import * as Y from "yjs";

export const serviceName = "vulcan-sync";
export type BoardElement = { id: string; kind: string; [key: string]: unknown };

export class BoardSession {
  readonly doc = new Y.Doc();
  private readonly elementsMap = this.doc.getMap<BoardElement>("elements");
  constructor(readonly boardId: string) {}
  setElement(element: BoardElement): void { this.doc.transact(() => this.elementsMap.set(element.id, element)); }
  applyElements(elements: BoardElement[]): void {
    this.doc.transact(() => {
      for (const element of elements) this.elementsMap.set(element.id, element);
    }, "ai-proposal");
  }
  elements(): BoardElement[] { return Array.from(this.elementsMap.values()).sort((a, b) => a.id.localeCompare(b.id)); }
}

export type StreamEvent = { id: number; streamId?: string; boardId: string; data: Buffer };
export interface BoardStream { append(boardId: string, data: Buffer): Promise<StreamEvent>; replay(boardId: string, afterId: number | string): Promise<StreamEvent[]>; findOperation(boardId: string, operationId: string): Promise<StreamEvent | undefined>; }

export class InMemoryBoardStream implements BoardStream {
  private readonly events: StreamEvent[] = [];
  async append(boardId: string, data: Buffer): Promise<StreamEvent> {
    const event = { id: this.events.length + 1, boardId, data: Buffer.from(data) };
    this.events.push(event);
    return event;
  }
  async replay(boardId: string, afterId: number | string): Promise<StreamEvent[]> {
    const afterSequence = typeof afterId === "number" ? afterId : Number(afterId.split("-")[0]);
    return this.events.filter((event) => event.boardId === boardId && event.id > afterSequence);
  }
  async findOperation(boardId: string, operationId: string): Promise<StreamEvent | undefined> {
    return this.events.find((event) => {
      if (event.boardId !== boardId) return false;
      try { return (JSON.parse(event.data.toString()) as { operationId?: string }).operationId === operationId; }
      catch { return false; }
    });
  }
}

type RedisClient = {
  xAdd(key: string, id: string, fields: Record<string, string>): Promise<string>;
  xRange(key: string, start: string, end: string): Promise<Array<{ id: string; message: Record<string, string> }> >;
};

export class RedisBoardStream implements BoardStream {
  constructor(private readonly client: RedisClient) {}
  async append(boardId: string, data: Buffer): Promise<StreamEvent> {
    const id = await this.client.xAdd(`board:${boardId}:ops`, "*", { data: data.toString("base64") });
    return { id: Number(id.split("-")[0]), streamId: id, boardId, data: Buffer.from(data) };
  }
  async replay(boardId: string, afterId: number | string): Promise<StreamEvent[]> {
    const cursor = typeof afterId === "string" ? afterId : `${afterId}-0`;
    const rows = await this.client.xRange(`board:${boardId}:ops`, cursor, "+");
    return rows.filter((row) => compareRedisIds(row.id, cursor) > 0).map((row) => ({ id: Number(row.id.split("-")[0]), streamId: row.id, boardId, data: Buffer.from(row.message.data, "base64") }));
  }
  async findOperation(boardId: string, operationId: string): Promise<StreamEvent | undefined> {
    const rows = await this.client.xRange(`board:${boardId}:ops`, "-", "+");
    for (const row of rows) {
      const data = Buffer.from(row.message.data, "base64");
      try {
        if ((JSON.parse(data.toString()) as { operationId?: string }).operationId === operationId) return { id: Number(row.id.split("-")[0]), streamId: row.id, boardId, data };
      } catch { /* corrupt entries are reported during replay */ }
    }
    return undefined;
  }
}

function compareRedisIds(left: string, right: string): number {
  const [leftMs, leftSeq] = left.split("-").map(Number);
  const [rightMs, rightSeq] = right.split("-").map(Number);
  return leftMs - rightMs || leftSeq - rightSeq;
}

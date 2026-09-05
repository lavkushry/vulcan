import { createHash } from "node:crypto";

export type Element = { id: string; kind: "text" | "shape" | "sticky" | "connector" | "freehand"; [key: string]: unknown };
export type Principal = { boardId: string; scope: "view" | "edit" };
export type BoardUpdate = { sequence: number; operationId: string; payload: Element; payloadHash: string };
export interface BoardUpdatePublisher { publish(update: BoardUpdate): Promise<void>; }

export class CapabilityError extends Error { constructor() { super("edit capability required"); this.name = "CapabilityError"; } }
export class DuplicateOperationError extends Error { constructor() { super("idempotency key reused with different payload"); this.name = "DuplicateOperationError"; } }

export class InMemoryPublisher implements BoardUpdatePublisher {
  events: BoardUpdate[] = [];
  async publish(update: BoardUpdate): Promise<void> { this.events.push(update); }
}

export class Board {
  readonly updates: BoardUpdate[] = [];
  private readonly operations = new Map<string, string>();
  constructor(readonly id: string, readonly workspaceId: string, private readonly publisher: BoardUpdatePublisher = new InMemoryPublisher()) {}

  async append(payload: Element, principal: Principal, operationId: string): Promise<BoardUpdate> {
    if (principal.boardId !== this.id || principal.scope !== "edit") throw new CapabilityError();
    const payloadHash = createHash("sha256").update(JSON.stringify(payload)).digest("hex");
    const priorHash = this.operations.get(operationId);
    if (priorHash && priorHash !== payloadHash) throw new DuplicateOperationError();
    if (priorHash) return this.updates.find((u) => u.operationId === operationId)!;
    const update: BoardUpdate = { sequence: this.updates.length + 1, operationId, payload, payloadHash };
    this.updates.push(update);
    this.operations.set(operationId, payloadHash);
    try { await this.publisher.publish(update); } catch (error) { this.updates.pop(); this.operations.delete(operationId); throw error; }
    return update;
  }
}

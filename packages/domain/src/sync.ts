export type ReplayEvent<T> = { boardId: string; sequence: number; payload: T };
export type QueueMessage = { channel: "ops" | "presence"; data: Buffer };
export type Clock = () => number;

export class ReplayLog<T> {
  private readonly events = new Map<string, ReplayEvent<T>[]>();
  append(boardId: string, sequence: number, payload: T): void {
    const list = this.events.get(boardId) ?? [];
    if (list.some((event) => event.sequence === sequence)) return;
    list.push({ boardId, sequence, payload });
    list.sort((a, b) => a.sequence - b.sequence);
    this.events.set(boardId, list);
  }
  replay(boardId: string, afterSequence: number): ReplayEvent<T>[] {
    return (this.events.get(boardId) ?? []).filter((event) => event.sequence > afterSequence);
  }
}

export class BoundedConnectionQueue {
  private readonly messages: Array<{ message: QueueMessage; insertedAt: number }> = [];
  private bytes = 0;
  constructor(private readonly clock: Clock = () => Date.now(), private readonly maxBytes = 5 * 1024 * 1024, private readonly presenceWindowMs = 150) {}
  push(message: QueueMessage): boolean {
    const now = this.clock();
    if (message.channel === "presence") {
      for (let i = this.messages.length - 1; i >= 0; i -= 1) {
        if (this.messages[i].message.channel === "presence" && now - this.messages[i].insertedAt >= this.presenceWindowMs) {
          this.bytes -= this.messages[i].message.data.byteLength;
          this.messages.splice(i, 1);
        }
      }
    }
    if (this.bytes + message.data.byteLength > this.maxBytes) return false;
    this.messages.push({ message, insertedAt: now });
    this.bytes += message.data.byteLength;
    return true;
  }
  take(): QueueMessage | undefined {
    const entry = this.messages.shift();
    if (!entry) return undefined;
    this.bytes -= entry.message.data.byteLength;
    return entry.message;
  }
}

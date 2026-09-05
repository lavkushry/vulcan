import { createHash } from "node:crypto";

export type AuditRecord = { id: number; requestId: string; actor: string; action: string; payload: Record<string, unknown>; previousHash: string; hash: string; timestamp: string };

export class AuditLedger {
  readonly records: AuditRecord[] = [];
  append(requestId: string, actor: string, action: string, payload: Record<string, unknown>): AuditRecord {
    const previousHash = this.records.at(-1)?.hash ?? "GENESIS";
    const timestamp = new Date().toISOString();
    const id = this.records.length + 1;
    const hash = this.compute({ id, requestId, actor, action, payload, previousHash, timestamp });
    const record = { id, requestId, actor, action, payload: { ...payload }, previousHash, hash, timestamp };
    this.records.push(record);
    return record;
  }
  verify(): boolean {
    return this.records.every((record, index) => {
      const { hash: _hash, ...content } = record;
      return record.previousHash === (index ? this.records[index - 1].hash : "GENESIS") && record.hash === this.compute(content);
    });
  }
  private compute(record: Omit<AuditRecord, "hash">): string {
    return createHash("sha256").update(JSON.stringify(record)).digest("hex");
  }
}

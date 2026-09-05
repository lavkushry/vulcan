export type StoredUpdate = { boardId: string; operationId: string; sequence: number; payload: Buffer };
export type StoredSnapshot = { boardId: string; sequence: number; payload: Buffer; checksum: string };

export interface BoardStore {
  append(boardId: string, operationId: string, payload: Buffer): Promise<StoredUpdate>;
  findOperation(boardId: string, operationId: string): Promise<StoredUpdate | undefined>;
  saveSnapshot(boardId: string, sequence: number, payload: Buffer): Promise<StoredSnapshot>;
  load(boardId: string): Promise<{ snapshot?: StoredSnapshot; updates: StoredUpdate[] }>;
}

import { createHash } from "node:crypto";

export class InMemoryBoardStore implements BoardStore {
  private readonly updates = new Map<string, StoredUpdate[]>();
  private readonly snapshots = new Map<string, StoredSnapshot>();
  async append(boardId: string, operationId: string, payload: Buffer): Promise<StoredUpdate> {
    const list = this.updates.get(boardId) ?? [];
    const existing = list.find((u) => u.operationId === operationId);
    if (existing) {
      if (!existing.payload.equals(payload)) throw new Error("idempotency key reused with different payload");
      return existing;
    }
    const update = { boardId, operationId, sequence: list.length + 1, payload: Buffer.from(payload) };
    list.push(update);
    this.updates.set(boardId, list);
    return update;
  }
  async findOperation(boardId: string, operationId: string): Promise<StoredUpdate | undefined> {
    return (this.updates.get(boardId) ?? []).find((update) => update.operationId === operationId);
  }
  async saveSnapshot(boardId: string, sequence: number, payload: Buffer): Promise<StoredSnapshot> {
    const snapshot = { boardId, sequence, payload: Buffer.from(payload), checksum: createHash("sha256").update(payload).digest("hex") };
    this.snapshots.set(boardId, snapshot);
    return snapshot;
  }
  async load(boardId: string): Promise<{ snapshot?: StoredSnapshot; updates: StoredUpdate[] }> {
    const snapshot = this.snapshots.get(boardId);
    return { snapshot, updates: (this.updates.get(boardId) ?? []).filter((u) => !snapshot || u.sequence > snapshot.sequence) };
  }
}

export type PgClient = { query(sql: string, params?: unknown[]): Promise<{ rows: Array<Record<string, unknown>> }> };

export class PostgresBoardStore implements BoardStore {
  constructor(private readonly client: PgClient) {}
  async append(boardId: string, operationId: string, payload: Buffer): Promise<StoredUpdate> {
    await this.client.query("BEGIN");
    try {
      await this.client.query("SELECT pg_advisory_xact_lock(hashtext($1))", [boardId]);
      const existing = await this.client.query("SELECT sequence, payload FROM board_updates WHERE board_id = $1 AND operation_id = $2 FOR UPDATE", [boardId, operationId]);
      if (existing.rows[0]) {
        const prior = Buffer.from(existing.rows[0].payload as Uint8Array);
        if (!prior.equals(payload)) throw new Error("idempotency key reused with different payload");
        await this.client.query("COMMIT");
        return { boardId, operationId, sequence: Number(existing.rows[0].sequence), payload: prior };
      }
      const inserted = await this.client.query("INSERT INTO board_updates (board_id, sequence, operation_id, payload) VALUES ($1, (SELECT COALESCE(MAX(sequence), 0) + 1 FROM board_updates WHERE board_id = $1), $2, $3) RETURNING sequence, payload", [boardId, operationId, payload]);
      await this.client.query("COMMIT");
      return { boardId, operationId, sequence: Number(inserted.rows[0].sequence), payload: Buffer.from(inserted.rows[0].payload as Uint8Array) };
    } catch (error) {
      await this.client.query("ROLLBACK");
      throw error;
    }
  }
  async findOperation(boardId: string, operationId: string): Promise<StoredUpdate | undefined> {
    const result = await this.client.query("SELECT sequence, operation_id, payload FROM board_updates WHERE board_id = $1 AND operation_id = $2", [boardId, operationId]);
    const row = result.rows[0];
    return row ? { boardId, operationId: String(row.operation_id), sequence: Number(row.sequence), payload: Buffer.from(row.payload as Uint8Array) } : undefined;
  }
  async saveSnapshot(boardId: string, sequence: number, payload: Buffer): Promise<StoredSnapshot> {
    const checksum = createHash("sha256").update(payload).digest("hex");
    await this.client.query("INSERT INTO board_snapshots (board_id, sequence, payload, checksum) VALUES ($1, $2, $3, $4) ON CONFLICT (board_id) DO UPDATE SET sequence = EXCLUDED.sequence, payload = EXCLUDED.payload, checksum = EXCLUDED.checksum", [boardId, sequence, payload, checksum]);
    return { boardId, sequence, payload: Buffer.from(payload), checksum };
  }
  async load(boardId: string): Promise<{ snapshot?: StoredSnapshot; updates: StoredUpdate[] }> {
    const snapshots = await this.client.query("SELECT sequence, payload, checksum FROM board_snapshots WHERE board_id = $1", [boardId]);
    const snapshotRow = snapshots.rows[0];
    const updates = await this.client.query("SELECT sequence, operation_id, payload FROM board_updates WHERE board_id = $1 AND sequence > $2 ORDER BY sequence", [boardId, snapshotRow?.sequence ?? 0]);
    return {
      snapshot: snapshotRow ? { boardId, sequence: Number(snapshotRow.sequence), payload: Buffer.from(snapshotRow.payload as Uint8Array), checksum: String(snapshotRow.checksum) } : undefined,
      updates: updates.rows.map((row) => ({ boardId, sequence: Number(row.sequence), operationId: String(row.operation_id), payload: Buffer.from(row.payload as Uint8Array) })),
    };
  }
}

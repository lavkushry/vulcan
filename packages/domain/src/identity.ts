import { randomUUID } from "node:crypto";

export type WorkspaceRecord = { id: string; name: string };
export type BoardRecord = { id: string; workspaceId: string; title: string };

export interface IdentityStore {
  createWorkspace(name: string, ownerId: string): Promise<WorkspaceRecord>;
  getWorkspace(id: string, userId: string): Promise<WorkspaceRecord | undefined>;
  createBoard(workspaceId: string, title: string, userId: string): Promise<BoardRecord | undefined>;
}

export class InMemoryIdentityStore implements IdentityStore {
  private readonly workspaces = new Map<string, WorkspaceRecord & { owners: Set<string> }>();
  private readonly boards = new Map<string, BoardRecord>();
  async createWorkspace(name: string, ownerId: string): Promise<WorkspaceRecord> {
    const workspace = { id: randomUUID(), name, owners: new Set([ownerId]) };
    this.workspaces.set(workspace.id, workspace);
    return { id: workspace.id, name: workspace.name };
  }
  async getWorkspace(id: string, userId: string): Promise<WorkspaceRecord | undefined> {
    const workspace = this.workspaces.get(id);
    return workspace && workspace.owners.has(userId) ? { id: workspace.id, name: workspace.name } : undefined;
  }
  async createBoard(workspaceId: string, title: string, userId: string): Promise<BoardRecord | undefined> {
    if (!await this.getWorkspace(workspaceId, userId)) return undefined;
    const board = { id: randomUUID(), workspaceId, title };
    this.boards.set(board.id, board);
    return board;
  }
}

export type IdentityPgClient = { query(sql: string, params?: unknown[]): Promise<{ rows: Array<Record<string, unknown>> }> };

export class PostgresIdentityStore implements IdentityStore {
  constructor(private readonly client: IdentityPgClient) {}
  async createWorkspace(name: string, ownerId: string): Promise<WorkspaceRecord> {
    const id = randomUUID();
    await this.client.query("BEGIN");
    try {
      await this.client.query("INSERT INTO workspaces (id, name) VALUES ($1, $2)", [id, name]);
      await this.client.query("INSERT INTO memberships (workspace_id, user_id, role) VALUES ($1, $2, 'owner')", [id, ownerId]);
      await this.client.query("COMMIT");
    } catch (error) { await this.client.query("ROLLBACK"); throw error; }
    return { id, name };
  }
  async getWorkspace(id: string, userId: string): Promise<WorkspaceRecord | undefined> {
    const result = await this.client.query("SELECT w.id, w.name FROM workspaces w JOIN memberships m ON m.workspace_id = w.id WHERE w.id = $1 AND m.user_id = $2", [id, userId]);
    const row = result.rows[0];
    return row ? { id: String(row.id), name: String(row.name) } : undefined;
  }
  async createBoard(workspaceId: string, title: string, userId: string): Promise<BoardRecord | undefined> {
    if (!await this.getWorkspace(workspaceId, userId)) return undefined;
    const id = randomUUID();
    await this.client.query("INSERT INTO boards (id, workspace_id, title) VALUES ($1, $2, $3)", [id, workspaceId, title]);
    return { id, workspaceId, title };
  }
}

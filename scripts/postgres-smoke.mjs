import { readFile } from "node:fs/promises";
import { randomUUID } from "node:crypto";
import pg from "pg";
import { PostgresBoardStore } from "../packages/domain/dist/persistence.js";
import { PostgresIdentityStore } from "../packages/domain/dist/identity.js";

const { Client } = pg;
const connectionString = process.env.DATABASE_URL || "postgres://vulcan:vulcan_local_only@127.0.0.1:5432/vulcan";
const client = new Client({ connectionString });
await client.connect();
try {
  for (const migration of ["migrations/001_whiteboard.sql", "migrations/002_identity_ai_audit.sql"]) await client.query(await readFile(migration, "utf8"));
  const userId = randomUUID();
  await client.query("INSERT INTO users (id, email) VALUES ($1, $2)", [userId, `${userId}@smoke.invalid`]);
  const identity = new PostgresIdentityStore(client);
  const workspace = await identity.createWorkspace("smoke", userId);
  const board = await identity.createBoard(workspace.id, "smoke", userId);
  if (!board) throw new Error("authorized board creation failed");
  const boardId = board.id;
  if (await identity.createBoard(workspace.id, "denied", randomUUID())) throw new Error("unauthorized board creation succeeded");
  const store = new PostgresBoardStore(client);
  const first = await store.append(boardId, "smoke-op", Buffer.from("payload"));
  const duplicate = await store.append(boardId, "smoke-op", Buffer.from("payload"));
  if (first.sequence !== duplicate.sequence) throw new Error("duplicate sequence changed");
  await store.saveSnapshot(boardId, first.sequence, Buffer.from("snapshot"));
  const loaded = await store.load(boardId);
  if (loaded.snapshot?.sequence !== first.sequence || loaded.updates.length !== 0) throw new Error("snapshot tail mismatch");
  console.log(JSON.stringify({ status: "ok", boardId, sequence: first.sequence }));
  await client.query("DELETE FROM boards WHERE id = $1", [boardId]);
  await client.query("DELETE FROM workspaces WHERE id = $1", [workspace.id]);
  await client.query("DELETE FROM users WHERE id = $1", [userId]);
} finally {
  await client.end();
}

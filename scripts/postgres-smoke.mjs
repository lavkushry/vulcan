import { readFile } from "node:fs/promises";
import { randomUUID } from "node:crypto";
import pg from "pg";
import { PostgresBoardStore } from "../packages/domain/dist/persistence.js";

const { Client } = pg;
const connectionString = process.env.DATABASE_URL || "postgres://vulcan:vulcan_local_only@127.0.0.1:5432/vulcan";
const client = new Client({ connectionString });
await client.connect();
try {
  for (const migration of ["migrations/001_whiteboard.sql", "migrations/002_identity_ai_audit.sql"]) await client.query(await readFile(migration, "utf8"));
  const workspaceId = randomUUID();
  const boardId = randomUUID();
  await client.query("INSERT INTO workspaces (id, name) VALUES ($1, $2)", [workspaceId, "smoke"]);
  await client.query("INSERT INTO boards (id, workspace_id, title) VALUES ($1, $2, $3)", [boardId, workspaceId, "smoke"]);
  const store = new PostgresBoardStore(client);
  const first = await store.append(boardId, "smoke-op", Buffer.from("payload"));
  const duplicate = await store.append(boardId, "smoke-op", Buffer.from("payload"));
  if (first.sequence !== duplicate.sequence) throw new Error("duplicate sequence changed");
  await store.saveSnapshot(boardId, first.sequence, Buffer.from("snapshot"));
  const loaded = await store.load(boardId);
  if (loaded.snapshot?.sequence !== first.sequence || loaded.updates.length !== 0) throw new Error("snapshot tail mismatch");
  console.log(JSON.stringify({ status: "ok", boardId, sequence: first.sequence }));
  await client.query("DELETE FROM boards WHERE id = $1", [boardId]);
  await client.query("DELETE FROM workspaces WHERE id = $1", [workspaceId]);
} finally {
  await client.end();
}

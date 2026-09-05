import assert from "node:assert/strict";
import test from "node:test";
import { InMemoryIdentityStore, PostgresIdentityStore } from "./identity.js";

test("in-memory identity store enforces workspace ownership", async () => {
  const store = new InMemoryIdentityStore();
  const workspace = await store.createWorkspace("Design", "u1");
  assert.equal((await store.getWorkspace(workspace.id, "u1"))?.name, "Design");
  assert.equal(await store.getWorkspace(workspace.id, "u2"), undefined);
  assert.equal((await store.createBoard(workspace.id, "Roadmap", "u1"))?.title, "Roadmap");
  assert.equal(await store.createBoard(workspace.id, "Nope", "u2"), undefined);
});

test("postgres identity store commits workspace and owner membership together", async () => {
  const calls: string[] = [];
  const client = { async query(sql: string) { calls.push(sql); return { rows: sql.startsWith("SELECT") ? [{ id: "w1", name: "Design" }] : [] }; } };
  const store = new PostgresIdentityStore(client);
  const workspace = await store.createWorkspace("Design", "u1");
  assert.equal(workspace.name, "Design");
  assert.deepEqual(calls.slice(0, 4), ["BEGIN", "INSERT INTO workspaces (id, name) VALUES ($1, $2)", "INSERT INTO memberships (workspace_id, user_id, role) VALUES ($1, $2, 'owner')", "COMMIT"]);
});

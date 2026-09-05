import assert from "node:assert/strict";
import test from "node:test";
import { InMemoryBoardStore } from "./persistence.js";
import { PostgresBoardStore } from "./persistence.js";

test("append-only store assigns contiguous sequences and loads snapshot tail", async () => {
  const store = new InMemoryBoardStore();
  await store.append("b1", "op-1", Buffer.from("a"));
  await store.append("b1", "op-2", Buffer.from("b"));
  await store.saveSnapshot("b1", 1, Buffer.from("snapshot"));
  const result = await store.load("b1");
  assert.equal(result.snapshot?.sequence, 1);
  assert.deepEqual(result.updates.map((u) => u.sequence), [2]);
});

test("duplicate operation IDs are idempotent and conflicting payloads fail", async () => {
  const store = new InMemoryBoardStore();
  await store.append("b1", "op-1", Buffer.from("a"));
  await store.append("b1", "op-1", Buffer.from("a"));
  assert.equal((await store.load("b1")).updates.length, 1);
  await assert.rejects(() => store.append("b1", "op-1", Buffer.from("different")), /idempotency/);
});

test("postgres adapter commits append before returning acknowledgement", async () => {
  const calls: string[] = [];
  const client = {
    async query(sql: string, _params?: unknown[]) {
      calls.push(sql.trim().split(" ")[0]);
      if (sql.includes("SELECT sequence")) return { rows: [] };
      if (sql.includes("INSERT INTO board_updates")) return { rows: [{ sequence: 1, payload: Buffer.from("a") }] };
      return { rows: [] };
    },
  };
  const update = await new PostgresBoardStore(client).append("b1", "op-1", Buffer.from("a"));
  assert.equal(update.sequence, 1);
  assert.deepEqual(calls.slice(0, 2), ["BEGIN", "SELECT"]);
  assert.equal(calls.at(-1), "COMMIT");
});

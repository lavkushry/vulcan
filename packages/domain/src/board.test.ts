import assert from "node:assert/strict";
import test from "node:test";
import { Board, CapabilityError, DuplicateOperationError, InMemoryPublisher } from "./board.js";

test("rejects writes without server-authoritative edit capability", async () => {
  const board = new Board("b1", "w1");
  await assert.rejects(() => board.append({ id: "e1", kind: "text", text: "x" }, { boardId: "b1", scope: "view" }, "op-1"), CapabilityError);
});

test("persists before publishing and is idempotent", async () => {
  const publisher = new InMemoryPublisher();
  const board = new Board("b1", "w1", publisher);
  const principal = { boardId: "b1", scope: "edit" as const };
  await board.append({ id: "e1", kind: "text", text: "x" }, principal, "op-1");
  await board.append({ id: "e1", kind: "text", text: "x" }, principal, "op-1");
  assert.equal(board.updates.length, 1);
  assert.equal(publisher.events.length, 1);
  assert.equal(publisher.events[0].sequence, 1);
});

test("rejects reuse of an idempotency key with different payload", async () => {
  const board = new Board("b1", "w1");
  const principal = { boardId: "b1", scope: "edit" as const };
  await board.append({ id: "e1", kind: "text", text: "x" }, principal, "op-1");
  await assert.rejects(() => board.append({ id: "e2", kind: "text", text: "y" }, principal, "op-1"), DuplicateOperationError);
});

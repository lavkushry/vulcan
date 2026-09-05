import assert from "node:assert/strict";
import test from "node:test";
import { BoundedConnectionQueue, ReplayLog } from "./sync.js";

test("replay log returns ordered events after a sequence and deduplicates delivery", () => {
  const log = new ReplayLog<{ value: string }>();
  log.append("b1", 1, { value: "a" });
  log.append("b1", 2, { value: "b" });
  assert.deepEqual(log.replay("b1", 1).map((e) => e.sequence), [2]);
  assert.deepEqual(log.replay("b1", 0).map((e) => e.sequence), [1, 2]);
});

test("connection queue enforces 5 MB bound and drops stale presence", () => {
  let now = 0;
  const queue = new BoundedConnectionQueue(() => now);
  assert.equal(queue.push({ channel: "presence", data: Buffer.from("old") }), true);
  now = 200;
  assert.equal(queue.push({ channel: "presence", data: Buffer.from("cursor") }), true);
  assert.equal(queue.take()?.channel, "presence");
  assert.equal(queue.push({ channel: "ops", data: Buffer.alloc(5 * 1024 * 1024) }), true);
  assert.equal(queue.push({ channel: "ops", data: Buffer.from("x") }), false);
});

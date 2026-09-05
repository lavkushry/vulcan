import assert from "node:assert/strict";
import test from "node:test";
import { FixedWindowLimiter } from "./rate-limit.js";

test("enforces request and board-write windows using an injectable clock", () => {
  let now = 0;
  const limiter = new FixedWindowLimiter(() => now);
  assert.equal(limiter.allow("user-1", 2, 1_000), true);
  assert.equal(limiter.allow("user-1", 2, 1_000), true);
  assert.equal(limiter.allow("user-1", 2, 1_000), false);
  now = 1_000;
  assert.equal(limiter.allow("user-1", 2, 1_000), true);
});

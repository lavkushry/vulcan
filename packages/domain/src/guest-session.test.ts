import assert from "node:assert/strict";
import test from "node:test";
import { GuestSessionRegistry } from "./guest-session.js";

test("guest sessions enforce capability, quota, expiry, and revocation cache bound", () => {
  let now = 0;
  const registry = new GuestSessionRegistry(() => now);
  const session = registry.issue("b1", "edit", 10, 2);
  assert.equal(registry.authorize(session, "b1", "edit"), true);
  assert.equal(registry.consumeWrite(session), true);
  assert.equal(registry.consumeWrite(session), true);
  assert.equal(registry.consumeWrite(session), false);
  registry.revoke(session);
  assert.equal(registry.authorize(session, "b1", "edit"), false);
  now = 11_000;
  assert.equal(registry.authorize(session, "b1", "edit"), false);
});

test("guest-session expiry uses the injected clock", () => {
  let now = 0;
  const registry = new GuestSessionRegistry(() => now);
  const session = registry.issue("b1", "view", 10, 0);
  assert.equal(registry.authorize(session, "b1", "view"), true);
  now = 10_000;
  assert.equal(registry.authorize(session, "b1", "view"), false);
});

test("guest write consumption rechecks edit capability and expiry", () => {
  let now = 0;
  const registry = new GuestSessionRegistry(() => now);
  const view = registry.issue("b1", "view", 10, 2);
  const edit = registry.issue("b1", "edit", 10, 2);
  assert.equal(registry.consumeWrite(view), false);
  assert.equal(registry.consumeWrite(edit), true);
  now = 10_000;
  assert.equal(registry.consumeWrite(edit), false);
});

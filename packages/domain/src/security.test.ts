import assert from "node:assert/strict";
import test from "node:test";
import { ShareLink, randomShareSecret } from "./security.js";

test("share links store only a hash and enforce scope/expiry/revocation", () => {
  const secret = randomShareSecret();
  const link = ShareLink.issue("b1", "edit", 60, secret);
  assert.equal(link.tokenHash.length, 64);
  assert.equal(link.verify(secret, "b1", "edit", Date.now()), true);
  assert.equal(link.verify(secret, "b2", "edit", Date.now()), false);
  link.revoke();
  assert.equal(link.verify(secret, "b1", "edit", Date.now()), false);
});

test("share links reject invalid capability scopes at runtime", () => {
  assert.throws(() => ShareLink.issue("b1", "admin" as never, 60, randomShareSecret()), /scope/);
});

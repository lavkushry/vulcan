import assert from "node:assert/strict";
import test from "node:test";
import { validateProposal } from "./ai.js";

test("accepts bounded ordinary elements and rejects mutation instructions", () => {
  const proposal = validateProposal({ elements: [{ id: "e1", kind: "text", text: "hello", x: 1, y: 2 }] });
  assert.equal(proposal.elements.length, 1);
  assert.throws(() => validateProposal({ mutateBoard: true }), /elements/);
});

test("rejects oversized or malformed geometry", () => {
  assert.throws(() => validateProposal({ elements: Array.from({ length: 1001 }, (_, i) => ({ id: String(i), kind: "shape" })) }), /maximum/);
  assert.throws(() => validateProposal({ elements: [{ id: "bad", kind: "shape", x: Infinity }] }), /geometry/);
});

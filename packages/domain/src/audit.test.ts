import assert from "node:assert/strict";
import test from "node:test";
import { AuditLedger } from "./audit.js";

test("audit ledger chains records and detects tampering", () => {
  const ledger = new AuditLedger();
  ledger.append("r1", "user-1", "board.update", { sequence: 1 });
  ledger.append("r1", "user-1", "board.update", { sequence: 2 });
  assert.equal(ledger.verify(), true);
  ledger.records[0].payload.sequence = 99;
  assert.equal(ledger.verify(), false);
});

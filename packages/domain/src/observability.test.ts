import assert from "node:assert/strict";
import test from "node:test";
import { CorrelationContext, InMemoryTracer, OtlpHttpTracer } from "./observability.js";

test("traces retain request, board, operation, and generation correlation", () => {
  const tracer = new InMemoryTracer();
  const context: CorrelationContext = { requestId: "r1", boardId: "b1", operationId: "o1", generationId: "g1" };
  tracer.record("board.update", context, { accepted: true });
  assert.deepEqual(tracer.spans[0], { name: "board.update", attributes: context, data: { accepted: true } });
});

test("OTLP tracer exports correlated spans without propagating exporter failures", async () => {
  let request: { url: string; body: string; headers: Record<string, string> } | undefined;
  const tracer = new OtlpHttpTracer("http://collector/v1/traces", async (url, init) => {
    request = { url, body: String(init?.body), headers: (init?.headers ?? {}) as Record<string, string> };
    throw new Error("collector unavailable");
  });
  tracer.record("board.update", { requestId: "r1", boardId: "b1", operationId: "o1", generationId: "g1" }, { accepted: true });
  await new Promise<void>((resolve) => setImmediate(resolve));
  assert.equal(request?.url, "http://collector/v1/traces");
  assert.equal(request?.headers["content-type"], "application/json");
  assert.match(request?.body || "", /request_id/);
  assert.match(request?.body || "", /generation_id/);
});

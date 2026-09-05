import assert from "node:assert/strict";
import test from "node:test";
import { GenerationQueue, RedisGenerationJobTransport } from "./index.js";

test("worker queue is idempotent and delegates validated generation", async () => {
  let calls = 0;
  const queue = new GenerationQueue(async () => { calls += 1; return { elements: [{ id: "e1", kind: "text" }] }; });
  const first = await queue.enqueue({ generationId: "g1", context: "ctx", prompt: "draw" });
  const second = await queue.enqueue({ generationId: "g1", context: "ctx", prompt: "draw" });
  assert.deepEqual(first, second);
  assert.equal(calls, 1);
});

test("Redis generation transport deduplicates jobs and records queued state", async () => {
  const calls: Array<[string, string]> = [];
  const client = {
    async set(key: string, value: string, options: { NX: true }) { calls.push(["set", `${key}=${value}:${options.NX}`]); return calls.filter(([op, value]) => op === "set" && value.startsWith(`${key}=`)).length === 1 ? "OK" : null; },
    async xAdd(key: string, _id: string, fields: Record<string, string>) { calls.push(["xadd", `${key}:${fields.data}`]); return "9-0"; },
    async hSet(key: string, fields: Record<string, string>) { calls.push(["hset", `${key}:${fields.status}`]); },
    async del(key: string) { calls.push(["del", key]); return 1; },
  };
  const transport = new RedisGenerationJobTransport(client);
  const job = { generationId: "g1", context: "ctx", prompt: "draw" };
  assert.deepEqual(await transport.enqueue(job), { status: "queued", id: "9-0", duplicate: false });
  assert.deepEqual(await transport.enqueue(job), { status: "queued", id: "vulcan:generation:g1", duplicate: true });
  assert.equal(calls.filter(([op]) => op === "xadd").length, 1);
  assert.equal(calls.some(([op, value]) => op === "set" && value.endsWith(":true")), true);
  assert.equal(calls.some(([op, value]) => op === "hset" && value.endsWith(":queued")), true);
});

test("Redis generation transport releases a claim when stream enqueue fails", async () => {
  let attempts = 0;
  const calls: string[] = [];
  const client = {
    async set() { return "OK" as const; },
    async xAdd() { attempts += 1; if (attempts === 1) throw new Error("redis unavailable"); return "10-0"; },
    async hSet() { calls.push("hset"); },
    async del(key: string) { calls.push(`del:${key}`); return 1; },
  };
  const transport = new RedisGenerationJobTransport(client);
  const job = { generationId: "g2", context: "ctx", prompt: "draw" };
  await assert.rejects(() => transport.enqueue(job), /redis unavailable/);
  assert.deepEqual(await transport.enqueue(job), { status: "queued", id: "10-0", duplicate: false });
  assert.deepEqual(calls, ["del:vulcan:generation:g2", "hset"]);
});

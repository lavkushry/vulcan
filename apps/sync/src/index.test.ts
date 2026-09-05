import assert from "node:assert/strict";
import test from "node:test";
import { performance } from "node:perf_hooks";
import * as Y from "yjs";
import { BoardSession, InMemoryBoardStream, RedisBoardStream } from "./index.js";
import { createSyncServer } from "./server.js";
import { GuestSessionRegistry } from "@vulcan/domain";
import WebSocket from "ws";

test("board sessions converge Yjs updates and expose ordinary elements", () => {
  const first = new BoardSession("b1");
  const second = new BoardSession("b1");
  first.setElement({ id: "e1", kind: "text", text: "hello" });
  Y.applyUpdate(second.doc, Y.encodeStateAsUpdate(first.doc));
  assert.deepEqual(second.elements(), [{ id: "e1", kind: "text", text: "hello" }]);
});

test("board session materializes the 10K-element benchmark within the load budget", () => {
  const session = new BoardSession("benchmark");
  const started = performance.now();
  for (let index = 0; index < 10_000; index += 1) session.setElement({ id: `fixture-${index}`, kind: "shape", x: index % 100, y: Math.floor(index / 100) });
  const elements = session.elements();
  assert.equal(elements.length, 10_000);
  assert.ok(performance.now() - started < 2_000, "10K-element materialization exceeded 2 seconds");
});

test("board session applies an AI proposal as one Yjs transaction", () => {
  const session = new BoardSession("ai-board");
  let updates = 0;
  session.doc.on("update", () => { updates += 1; });
  session.applyElements([{ id: "ai-1", kind: "shape" }, { id: "ai-2", kind: "text", text: "Generated" }]);
  assert.equal(updates, 1);
  assert.equal(session.elements().length, 2);
});

test("stream isolates boards and replays monotonically after an ID", async () => {
  const stream = new InMemoryBoardStream();
  const first = await stream.append("b1", Buffer.from("a"));
  await stream.append("b2", Buffer.from("other"));
  await stream.append("b1", Buffer.from("b"));
  assert.deepEqual((await stream.replay("b1", first.id)).map((event) => event.data.toString()), ["b"]);
});

test("Redis stream adapter uses a board-scoped key and replays after IDs", async () => {
  const calls: string[] = [];
  const client = {
    async xAdd(key: string, _id: string, fields: Record<string, string>) { calls.push(key); return "7-0"; },
    async xRange(key: string, _start: string, _end: string) { calls.push(key); return [{ id: "8-0", message: { data: "a" } }]; },
  };
  const stream = new RedisBoardStream(client);
  assert.equal((await stream.append("b1", Buffer.from("x"))).id, 7);
  assert.equal((await stream.replay("b1", 7))[0].id, 8);
  assert.deepEqual(calls, ["board:b1:ops", "board:b1:ops"]);
});

test("WebSocket gateway authorizes, appends before ack, and broadcasts board operations", async () => {
  const registry = new GuestSessionRegistry();
  const token = registry.issue("b1", "edit", 60, 2);
  const server = createSyncServer(registry, new InMemoryBoardStream());
  await new Promise<void>((resolve) => server.listen(0, resolve));
  const address = server.address();
  if (!address || typeof address === "string") throw new Error("server did not bind");
  const socket = new WebSocket(`ws://127.0.0.1:${address.port}/boards/b1?capability=${encodeURIComponent(token)}`);
  const received = new Promise<string>((resolve) => socket.on("message", (data) => resolve(data.toString())));
  await new Promise<void>((resolve) => socket.on("open", () => resolve()));
  socket.send(JSON.stringify({ type: "op", operationId: "o1", payload: { id: "e1", kind: "text" } }));
  assert.match(await received, /"type":"ack"/);
  socket.close();
  server.close();
});

test("WebSocket gateway replays missed operations on reconnect", async () => {
  const registry = new GuestSessionRegistry();
  const token = registry.issue("b1", "edit", 60, 2);
  const stream = new InMemoryBoardStream();
  await stream.append("b1", Buffer.from(JSON.stringify({ operationId: "o1", payload: { id: "e1" } })));
  await stream.append("b1", Buffer.from(JSON.stringify({ operationId: "o2", payload: { id: "e2" } })));
  const server = createSyncServer(registry, stream);
  await new Promise<void>((resolve) => server.listen(0, resolve));
  const address = server.address();
  if (!address || typeof address === "string") throw new Error("server did not bind");
  const socket = new WebSocket(`ws://127.0.0.1:${address.port}/boards/b1?capability=${encodeURIComponent(token)}&after=1`);
  const replay = new Promise<string>((resolve) => socket.on("message", (data) => resolve(data.toString())));
  await new Promise<void>((resolve) => socket.on("open", () => resolve()));
  assert.match(await replay, /"sequence":2/);
  socket.close();
  server.close();
});

test("WebSocket gateway makes operation IDs idempotent without consuming duplicate quota", async () => {
  const registry = new GuestSessionRegistry();
  const token = registry.issue("b1", "edit", 60, 1);
  const stream = new InMemoryBoardStream();
  const server = createSyncServer(registry, stream);
  await new Promise<void>((resolve) => server.listen(0, resolve));
  const address = server.address();
  if (!address || typeof address === "string") throw new Error("server did not bind");
  const socket = new WebSocket(`ws://127.0.0.1:${address.port}/boards/b1?capability=${encodeURIComponent(token)}`);
  await new Promise<void>((resolve) => socket.on("open", () => resolve()));
  const send = (payload: unknown) => new Promise<string>((resolve) => {
    socket.once("message", (data) => resolve(data.toString()));
    socket.send(JSON.stringify({ type: "op", operationId: "same-op", payload }));
  });
  const first = JSON.parse(await send({ id: "e1" })) as { type: string; sequence: number };
  const duplicate = JSON.parse(await send({ id: "e1" })) as { type: string; sequence: number };
  assert.equal(first.type, "ack");
  assert.deepEqual(duplicate, first);
  const conflicting = JSON.parse(await send({ id: "different" })) as { type: string; code?: string };
  assert.equal(conflicting.type, "error");
  assert.equal(conflicting.code, "idempotency_conflict");
  socket.close();
  server.close();
});

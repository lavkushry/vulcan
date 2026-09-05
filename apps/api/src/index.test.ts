import assert from "node:assert/strict";
import test from "node:test";
import { createApiServer } from "./index.js";
import { GuestSessionRegistry, InMemoryBoardStore, InMemoryTracer } from "@vulcan/domain";

test("API exposes health and rejects unauthorized board writes", async () => {
  const server = createApiServer();
  await new Promise<void>((resolve) => server.listen(0, resolve));
  const address = server.address();
  if (!address || typeof address === "string") throw new Error("server did not bind");
  const base = `http://127.0.0.1:${address.port}`;
  assert.equal((await fetch(`${base}/healthz`)).status, 200);
  const denied = await fetch(`${base}/v1/boards/b1/updates`, { method: "POST", body: JSON.stringify({ operationId: "o1", payload: { id: "e1" } }), headers: { "content-type": "application/json" } });
  assert.equal(denied.status, 403);
  server.close();
});

test("API rejects request bodies larger than 1 MiB", async () => {
  const server = createApiServer();
  await new Promise<void>((resolve) => server.listen(0, "127.0.0.1", () => resolve()));
  const address = server.address();
  if (!address || typeof address === "string") throw new Error("server did not bind");
  const response = await fetch(`http://127.0.0.1:${address.port}/v1/workspaces`, { method: "POST", headers: { "content-type": "application/json", "x-user-id": "u1" }, body: JSON.stringify({ name: "x".repeat(1_048_577) }) });
  assert.equal(response.status, 413);
  await new Promise<void>((resolve, reject) => server.close((error) => error ? reject(error) : resolve()));
});

test("API creates workspaces and server-authorized boards", async () => {
  const server = createApiServer();
  await new Promise<void>((resolve) => server.listen(0, "127.0.0.1", () => resolve()));
  const address = server.address();
  assert.equal(typeof address === "object" && address ? true : false, true);
  const base = `http://127.0.0.1:${(address as { port: number }).port}`;
  const headers = { "content-type": "application/json", "x-user-id": "user-1" };
  const createdWorkspace = await fetch(`${base}/v1/workspaces`, { method: "POST", headers, body: JSON.stringify({ name: "Design" }) });
  assert.equal(createdWorkspace.status, 201);
  const workspace = await createdWorkspace.json() as { id: string };
  const denied = await fetch(`${base}/v1/boards`, { method: "POST", headers: { ...headers, "x-user-id": "user-2" }, body: JSON.stringify({ workspaceId: workspace.id, title: "Roadmap" }) });
  assert.equal(denied.status, 403);
  const createdBoard = await fetch(`${base}/v1/boards`, { method: "POST", headers, body: JSON.stringify({ workspaceId: workspace.id, title: "Roadmap" }) });
  assert.equal(createdBoard.status, 201);
  const board = await createdBoard.json() as { id: string; capability: string };
  assert.equal(typeof board.capability, "string");
  const loaded = await fetch(`${base}/v1/boards/${board.id}`, { headers: { "x-capability": board.capability } });
  assert.equal(loaded.status, 200);
  await new Promise<void>((resolve, reject) => server.close((error) => error ? reject(error) : resolve()));
});

test("API makes workspace and board creation idempotent", async () => {
  const server = createApiServer();
  await new Promise<void>((resolve) => server.listen(0, "127.0.0.1", resolve));
  const address = server.address();
  if (!address || typeof address === "string") throw new Error("server did not bind");
  const base = `http://127.0.0.1:${address.port}`;
  const workspaceHeaders = { "content-type": "application/json", "x-user-id": "u1", "idempotency-key": "workspace-key" };
  const firstWorkspace = await fetch(`${base}/v1/workspaces`, { method: "POST", headers: workspaceHeaders, body: JSON.stringify({ name: "Design" }) });
  const secondWorkspace = await fetch(`${base}/v1/workspaces`, { method: "POST", headers: workspaceHeaders, body: JSON.stringify({ name: "Design" }) });
  assert.equal(firstWorkspace.status, 201); assert.equal(secondWorkspace.status, 200);
  const workspace = await firstWorkspace.json() as { id: string };
  const boardHeaders = { "content-type": "application/json", "x-user-id": "u1", "idempotency-key": "board-key" };
  const firstBoard = await fetch(`${base}/v1/boards`, { method: "POST", headers: boardHeaders, body: JSON.stringify({ workspaceId: workspace.id, title: "Roadmap" }) });
  const secondBoard = await fetch(`${base}/v1/boards`, { method: "POST", headers: boardHeaders, body: JSON.stringify({ workspaceId: workspace.id, title: "Roadmap" }) });
  assert.equal(firstBoard.status, 201); assert.equal(secondBoard.status, 200);
  await new Promise<void>((resolve, reject) => server.close((error) => error ? reject(error) : resolve()));
});

test("API persists authorized updates before acknowledging and is idempotent", async () => {
  const server = createApiServer();
  await new Promise<void>((resolve) => server.listen(0, resolve));
  const address = server.address();
  if (!address || typeof address === "string") throw new Error("server did not bind");
  const url = `http://127.0.0.1:${address.port}/v1/boards/b1/updates`;
  const registry = new GuestSessionRegistry();
  const token = registry.issue("b1", "edit", 60, 1);
  server.close();
  const authorizedServer = createApiServer(registry);
  await new Promise<void>((resolve) => authorizedServer.listen(0, resolve));
  const bound = authorizedServer.address();
  if (!bound || typeof bound === "string") throw new Error("server did not bind");
  const init = { method: "POST", headers: { "content-type": "application/json", "x-capability": token }, body: JSON.stringify({ operationId: "o1", payload: { id: "e1", kind: "text" } }) };
  const authorizedUrl = `http://127.0.0.1:${bound.port}/v1/boards/b1/updates`;
  assert.equal((await fetch(authorizedUrl, init)).status, 201);
  assert.equal((await fetch(authorizedUrl, init)).status, 200);
  assert.equal((await fetch(authorizedUrl, { ...init, body: JSON.stringify({ operationId: "o2", payload: { id: "e2", kind: "text" } }) })).status, 429);
  authorizedServer.close();
});

test("API does not persist or acknowledge a new operation after quota exhaustion", async () => {
  const registry = new GuestSessionRegistry();
  const token = registry.issue("b1", "edit", 60, 1);
  const server = createApiServer(registry);
  await new Promise<void>((resolve) => server.listen(0, resolve));
  const address = server.address();
  if (!address || typeof address === "string") throw new Error("server did not bind");
  const url = `http://127.0.0.1:${address.port}/v1/boards/b1/updates`;
  const headers = { "content-type": "application/json", "x-capability": token };
  const first = { operationId: "o1", payload: { id: "e1" } };
  const rejected = { operationId: "o2", payload: { id: "e2" } };
  assert.equal((await fetch(url, { method: "POST", headers, body: JSON.stringify(first) })).status, 201);
  assert.equal((await fetch(url, { method: "POST", headers, body: JSON.stringify(rejected) })).status, 429);
  assert.equal((await fetch(url, { method: "POST", headers, body: JSON.stringify(rejected) })).status, 429);
  server.close();
});

test("API exposes AI preview and one-time confirmation behind capability auth", async () => {
  const registry = new GuestSessionRegistry();
  const token = registry.issue("b1", "edit", 60, 10);
  const server = createApiServer(registry, async () => ({ elements: [{ id: "e1", kind: "shape" }] }));
  await new Promise<void>((resolve) => server.listen(0, resolve));
  const address = server.address();
  if (!address || typeof address === "string") throw new Error("server did not bind");
  const headers = { "content-type": "application/json", "x-capability": token, "x-board-id": "b1" };
  const base = `http://127.0.0.1:${address.port}`;
  const generated = await fetch(`${base}/v1/generations`, { method: "POST", headers, body: JSON.stringify({ generationId: "g1", context: "ctx", prompt: "draw" }) });
  assert.equal(generated.status, 200);
  assert.equal((await fetch(`${base}/v1/generations/g1`, { headers })).status, 200);
  assert.equal((await fetch(`${base}/v1/generations/g1`, { headers: { "x-board-id": "b1" } })).status, 403);
  const accepted = await fetch(`${base}/v1/generations/g1/accept`, { method: "POST", headers });
  assert.equal(accepted.status, 200);
  assert.equal((await fetch(`${base}/v1/generations/g1/accept`, { method: "POST", headers })).status, 409);
  server.close();
});

test("API enforces injectable request and board-write rate limits", async () => {
  let now = 0;
  const registry = new GuestSessionRegistry();
  const token = registry.issue("b1", "edit", 60, 10);
  const server = createApiServer(registry, undefined, undefined, {
    clock: () => now,
    requestsPerWindow: 2,
    requestWindowMs: 1_000,
    writesPerWindow: 1,
    writeWindowMs: 1_000,
  });
  await new Promise<void>((resolve) => server.listen(0, resolve));
  const address = server.address();
  if (!address || typeof address === "string") throw new Error("server did not bind");
  const url = `http://127.0.0.1:${address.port}/v1/boards/b1/updates`;
  const headers = { "content-type": "application/json", "x-capability": token };
  const send = (operationId: string) => fetch(url, { method: "POST", headers, body: JSON.stringify({ operationId, payload: { id: operationId } }) });
  assert.equal((await send("o1")).status, 201);
  assert.equal((await send("o2")).status, 429);
  now = 1_000;
  assert.equal((await send("o2")).status, 201);
  assert.equal((await send("o3")).status, 429);
  server.close();
});

test("API applies request limits to the source even when capabilities rotate", async () => {
  let now = 0;
  const registry = new GuestSessionRegistry();
  const first = registry.issue("b1", "view", 60, 0);
  const second = registry.issue("b1", "view", 60, 0);
  const server = createApiServer(registry, undefined, undefined, { clock: () => now, requestsPerWindow: 2, requestWindowMs: 1_000 });
  await new Promise<void>((resolve) => server.listen(0, resolve));
  const address = server.address();
  if (!address || typeof address === "string") throw new Error("server did not bind");
  const url = `http://127.0.0.1:${address.port}/v1/boards/b1`;
  const read = (token: string) => fetch(url, { headers: { "x-capability": token } });
  assert.equal((await read(first)).status, 200);
  assert.equal((await read(second)).status, 200);
  assert.equal((await read(first)).status, 429);
  now = 1_000;
  assert.equal((await read(second)).status, 200);
  server.close();
});

test("API records correlated request, board, operation, and generation IDs", async () => {
  const tracer = new InMemoryTracer();
  const registry = new GuestSessionRegistry();
  const token = registry.issue("b1", "edit", 60, 2);
  const server = createApiServer(registry, undefined, undefined, { tracer });
  await new Promise<void>((resolve) => server.listen(0, resolve));
  const address = server.address();
  if (!address || typeof address === "string") throw new Error("server did not bind");
  const headers = { "content-type": "application/json", "x-capability": token, "x-board-id": "b1" };
  const base = `http://127.0.0.1:${address.port}`;
  await fetch(`${base}/v1/boards/b1/updates`, { method: "POST", headers, body: JSON.stringify({ operationId: "o1", payload: { id: "e1" } }) });
  await fetch(`${base}/v1/generations`, { method: "POST", headers, body: JSON.stringify({ generationId: "g1", context: "ctx", prompt: "draw" }) });
  assert.equal(tracer.spans.some((span) => span.attributes.boardId === "b1" && span.attributes.operationId === "o1"), true);
  assert.equal(tracer.spans.some((span) => span.attributes.boardId === "b1" && span.attributes.generationId === "g1"), true);
  server.close();
});

test("API authorizes board and snapshot reads with view capabilities", async () => {
  const registry = new GuestSessionRegistry();
  const token = registry.issue("b1", "view", 60, 0);
  const store = new InMemoryBoardStore();
  await store.append("b1", "o1", Buffer.from(JSON.stringify({ id: "e1", kind: "text" })));
  await store.saveSnapshot("b1", 1, Buffer.from(JSON.stringify({ elements: [{ id: "e1" }] })));
  const server = createApiServer(registry, undefined, store);
  await new Promise<void>((resolve) => server.listen(0, resolve));
  const address = server.address();
  if (!address || typeof address === "string") throw new Error("server did not bind");
  const base = `http://127.0.0.1:${address.port}`;
  assert.equal((await fetch(`${base}/v1/boards/b1`, { headers: { "x-capability": token } })).status, 200);
  const snapshot = await fetch(`${base}/v1/boards/b1/snapshot`, { headers: { "x-capability": token } });
  assert.equal(snapshot.status, 200);
  assert.equal((await snapshot.json()).sequence, 1);
  assert.equal((await fetch(`${base}/v1/boards/b1`)).status, 403);
  server.close();
});

test("API issues scoped expiring share links behind edit authorization", async () => {
  const registry = new GuestSessionRegistry();
  const ownerToken = registry.issue("b1", "edit", 60, 2);
  const server = createApiServer(registry);
  await new Promise<void>((resolve) => server.listen(0, resolve));
  const address = server.address();
  if (!address || typeof address === "string") throw new Error("server did not bind");
  const base = `http://127.0.0.1:${address.port}`;
  const response = await fetch(`${base}/v1/boards/b1/share-links`, {
    method: "POST",
    headers: { "content-type": "application/json", "x-capability": ownerToken },
    body: JSON.stringify({ scope: "view", ttlSeconds: 300, writeQuota: 0 }),
  });
  assert.equal(response.status, 201);
  const issued = await response.json() as { token: string; scope: string; expiresInSeconds: number };
  assert.equal(issued.scope, "view");
  assert.equal(issued.expiresInSeconds, 300);
  assert.equal((await fetch(`${base}/v1/boards/b1`, { headers: { "x-capability": issued.token } })).status, 200);
  assert.equal((await fetch(`${base}/v1/boards/b1/share-links`, { method: "POST", headers: { "content-type": "application/json", "x-capability": ownerToken }, body: JSON.stringify({ scope: "view", ttlSeconds: 86_401, writeQuota: 0 }) })).status, 400);
  server.close();
});

test("API lets an editor revoke a share link for the same board", async () => {
  const registry = new GuestSessionRegistry();
  const ownerToken = registry.issue("b1", "edit", 60, 10);
  const server = createApiServer(registry);
  await new Promise<void>((resolve) => server.listen(0, "127.0.0.1", resolve));
  const address = server.address();
  if (!address || typeof address === "string") throw new Error("server did not bind");
  const base = `http://127.0.0.1:${address.port}`;
  const issued = await fetch(`${base}/v1/boards/b1/share-links`, { method: "POST", headers: { "content-type": "application/json", "x-capability": ownerToken }, body: JSON.stringify({ scope: "edit", ttlSeconds: 60, writeQuota: 1 }) });
  const token = (await issued.json() as { token: string }).token;
  const revoked = await fetch(`${base}/v1/boards/b1/share-links/revoke`, { method: "POST", headers: { "content-type": "application/json", "x-capability": ownerToken }, body: JSON.stringify({ token }) });
  assert.equal(revoked.status, 204);
  assert.equal(registry.authorize(token, "b1", "view"), false);
  await new Promise<void>((resolve, reject) => server.close((error) => error ? reject(error) : resolve()));
});

test("API idempotency lookup survives snapshots without consuming quota", async () => {
  const registry = new GuestSessionRegistry();
  const token = registry.issue("b1", "edit", 60, 0);
  const store = new InMemoryBoardStore();
  await store.append("b1", "o1", Buffer.from(JSON.stringify({ id: "e1" })));
  await store.saveSnapshot("b1", 1, Buffer.from("snapshot"));
  const server = createApiServer(registry, undefined, store);
  await new Promise<void>((resolve) => server.listen(0, resolve));
  const address = server.address();
  if (!address || typeof address === "string") throw new Error("server did not bind");
  const response = await fetch(`http://127.0.0.1:${address.port}/v1/boards/b1/updates`, { method: "POST", headers: { "content-type": "application/json", "x-capability": token }, body: JSON.stringify({ operationId: "o1", payload: { id: "e1" } }) });
  assert.equal(response.status, 200);
  server.close();
});

test("API keeps a generation ID bound to its original board", async () => {
  const registry = new GuestSessionRegistry();
  const tokenA = registry.issue("a", "edit", 60, 2);
  const tokenB = registry.issue("b", "edit", 60, 2);
  const server = createApiServer(registry, async () => ({ elements: [] }));
  await new Promise<void>((resolve) => server.listen(0, resolve));
  const address = server.address();
  if (!address || typeof address === "string") throw new Error("server did not bind");
  const base = `http://127.0.0.1:${address.port}/v1/generations`;
  const make = (token: string, boardId: string) => fetch(base, { method: "POST", headers: { "content-type": "application/json", "x-capability": token, "x-board-id": boardId }, body: JSON.stringify({ generationId: "same", context: "ctx", prompt: "draw" }) });
  assert.equal((await make(tokenA, "a")).status, 200);
  assert.equal((await make(tokenB, "b")).status, 409);
  server.close();
});

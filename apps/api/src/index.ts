import { createServer, type IncomingMessage, type Server, type ServerResponse } from "node:http";
import { randomUUID } from "node:crypto";
import { AiGenerationService, FixedWindowLimiter, GuestSessionRegistry, hashShareSecret, InMemoryBoardStore, type BoardStore, type Tracer } from "@vulcan/domain";

export const serviceName = "vulcan-api";
type Model = (context: string, prompt: string, repair: boolean) => Promise<unknown>;
export type ApiLimitOptions = {
  clock?: () => number;
  requestsPerWindow?: number;
  requestWindowMs?: number;
  writesPerWindow?: number;
  writeWindowMs?: number;
  tracer?: Tracer;
};

async function body(request: IncomingMessage): Promise<Record<string, unknown>> {
  const chunks: Buffer[] = [];
  for await (const chunk of request) chunks.push(Buffer.from(chunk));
  return JSON.parse(Buffer.concat(chunks).toString("utf8") || "{}");
}

function respond(response: ServerResponse, status: number, value: unknown, requestId: string): void {
  response.statusCode = status;
  response.setHeader("content-type", "application/json");
  response.setHeader("x-request-id", requestId);
  if (status >= 400 && value && typeof value === "object" && typeof (value as { error?: unknown }).error === "string") {
    const message = (value as { error: string }).error;
    value = { error: { code: `http_${status}`, message, requestId, retryable: status >= 500 } };
  }
  response.end(JSON.stringify(value));
}

function decodePayload(payload: Buffer): unknown {
  try { return JSON.parse(payload.toString("utf8")); }
  catch { return { encoding: "base64", value: payload.toString("base64") }; }
}

export function createApiServer(registry = new GuestSessionRegistry(), model: Model = async () => ({ elements: [] }), store: BoardStore = new InMemoryBoardStore(), limits: ApiLimitOptions = {}): Server {
  const generationBoards = new Map<string, string>();
  const generations = new AiGenerationService(model);
  const clock = limits.clock ?? (() => Date.now());
  const requestLimiter = new FixedWindowLimiter(clock);
  const writeLimiter = new FixedWindowLimiter(clock);
  const requestsPerWindow = limits.requestsPerWindow ?? 60;
  const requestWindowMs = limits.requestWindowMs ?? 60_000;
  const writesPerWindow = limits.writesPerWindow ?? 10;
  const writeWindowMs = limits.writeWindowMs ?? 1_000;
  return createServer(async (request, response) => {
    const requestId = request.headers["x-request-id"]?.toString() || randomUUID();
    try {
      if (request.method === "GET" && request.url === "/healthz") return respond(response, 200, { status: "ok" }, requestId);
      if (request.method === "GET" && request.url === "/readyz") return respond(response, 200, { status: "ready" }, requestId);
      const capability = request.headers["x-capability"]?.toString() || "";
      const principalKey = capability ? `cap:${hashShareSecret(capability)}` : `ip:${request.socket.remoteAddress || "anonymous"}`;
      if (!requestLimiter.allow(principalKey, requestsPerWindow, requestWindowMs)) return respond(response, 429, { error: "request rate limit exceeded" }, requestId);
      const match = request.url?.match(/^\/v1\/boards\/([^/]+)\/updates$/);
      const shareLinksMatch = request.url?.match(/^\/v1\/boards\/([^/]+)\/share-links$/);
      const snapshotMatch = request.url?.match(/^\/v1\/boards\/([^/]+)\/snapshot$/);
      const boardMatch = request.url?.match(/^\/v1\/boards\/([^/]+)$/);
      const generationGet = request.url?.match(/^\/v1\/generations\/([^/]+)$/);
      const accept = request.url?.match(/^\/v1\/generations\/([^/]+)\/accept$/);
      limits.tracer?.record("http.request", {
        requestId,
        boardId: match?.[1] || request.headers["x-board-id"]?.toString(),
        generationId: accept?.[1],
      });
      if (request.method === "GET" && (snapshotMatch || boardMatch)) {
        const boardId = (snapshotMatch || boardMatch)?.[1] as string;
        if (!registry.authorize(capability, boardId, "view")) return respond(response, 403, { error: "view capability required" }, requestId);
        const loaded = await store.load(boardId);
        if (snapshotMatch) {
          if (!loaded.snapshot) return respond(response, 404, { error: "snapshot not found" }, requestId);
          return respond(response, 200, { boardId, sequence: loaded.snapshot.sequence, payload: decodePayload(loaded.snapshot.payload), checksum: loaded.snapshot.checksum }, requestId);
        }
        return respond(response, 200, {
          boardId,
          snapshot: loaded.snapshot ? { sequence: loaded.snapshot.sequence, payload: decodePayload(loaded.snapshot.payload), checksum: loaded.snapshot.checksum } : undefined,
          updates: loaded.updates.map((update) => ({ operationId: update.operationId, sequence: update.sequence, payload: decodePayload(update.payload) })),
        }, requestId);
      }
      if (request.method === "POST" && shareLinksMatch) {
        const boardId = shareLinksMatch[1];
        if (!registry.authorize(capability, boardId, "edit")) return respond(response, 403, { error: "edit capability required" }, requestId);
        const input = await body(request);
        const scope = input.scope;
        const ttlSeconds = input.ttlSeconds;
        const writeQuota = input.writeQuota;
        if ((scope !== "view" && scope !== "edit") || typeof ttlSeconds !== "number" || !Number.isInteger(ttlSeconds) || ttlSeconds < 1 || ttlSeconds > 24 * 60 * 60 || typeof writeQuota !== "number" || !Number.isInteger(writeQuota) || writeQuota < 0) return respond(response, 400, { error: "scope, ttlSeconds, and non-negative integer writeQuota required" }, requestId);
        const token = registry.issue(boardId, scope, ttlSeconds, writeQuota);
        return respond(response, 201, { token, boardId, scope, expiresInSeconds: ttlSeconds }, requestId);
      }
      if (request.method === "POST" && match) {
        if (!registry.authorize(capability, match[1], "edit")) return respond(response, 403, { error: "edit capability required" }, requestId);
        const input = await body(request);
        if (typeof input.operationId !== "string" || !input.operationId) return respond(response, 400, { error: "operationId required" }, requestId);
        limits.tracer?.record("board.update", { requestId, boardId: match[1], operationId: input.operationId });
        const payload = Buffer.from(JSON.stringify(input.payload));
        const existing = await store.findOperation(match[1], input.operationId);
        if (existing) {
          if (!existing.payload.equals(payload)) return respond(response, 409, { error: "idempotency conflict" }, requestId);
          return respond(response, 200, { operationId: existing.operationId, payload: JSON.parse(existing.payload.toString()), sequence: existing.sequence }, requestId);
        }
        if (!writeLimiter.allow(`${principalKey}:${match[1]}`, writesPerWindow, writeWindowMs)) return respond(response, 429, { error: "board write rate limit exceeded" }, requestId);
        if (!registry.consumeWrite(capability)) return respond(response, 429, { error: "write quota exceeded" }, requestId);
        let stored;
        try { stored = await store.append(match[1], input.operationId, payload); }
        catch (error) { if (String(error).includes("idempotency")) return respond(response, 409, { error: "idempotency conflict" }, requestId); throw error; }
        return respond(response, 201, { operationId: stored.operationId, payload: JSON.parse(stored.payload.toString()), sequence: stored.sequence }, requestId);
      }
      if (request.method === "POST" && request.url === "/v1/generations") {
        const boardId = request.headers["x-board-id"]?.toString() || "";
        if (!registry.authorize(capability, boardId, "edit")) return respond(response, 403, { error: "edit capability required" }, requestId);
        const input = await body(request) as { generationId?: string; context?: string; prompt?: string };
        if (typeof input.generationId !== "string" || !input.generationId || typeof input.prompt !== "string" || typeof input.context !== "string") return respond(response, 400, { error: "generationId, context, and prompt required" }, requestId);
        limits.tracer?.record("generation.request", { requestId, boardId, generationId: input.generationId });
        const priorBoard = generationBoards.get(input.generationId);
        if (priorBoard && priorBoard !== boardId) return respond(response, 409, { error: "generation ID already belongs to another board" }, requestId);
        generationBoards.set(input.generationId, boardId);
        return respond(response, 200, await generations.generate(input.generationId, input.context, input.prompt), requestId);
      }
      if (request.method === "GET" && generationGet) {
        const generationId = generationGet[1];
        const boardId = request.headers["x-board-id"]?.toString() || "";
        if (generationBoards.get(generationId) !== boardId || !registry.authorize(capability, boardId, "view")) return respond(response, 403, { error: "view capability required" }, requestId);
        const result = generations.get(generationId);
        if (!result) return respond(response, 404, { error: "generation not found" }, requestId);
        return respond(response, 200, result, requestId);
      }
      if (request.method === "POST" && accept) {
        const boardId = request.headers["x-board-id"]?.toString() || "";
        const capability = request.headers["x-capability"]?.toString() || "";
        if (generationBoards.get(accept[1]) !== boardId || !registry.authorize(capability, boardId, "edit")) return respond(response, 403, { error: "edit capability required" }, requestId);
        try { return respond(response, 200, await generations.accept(accept[1]), requestId); }
        catch (error) { if (String(error).includes("already accepted")) return respond(response, 409, { error: "generation already accepted" }, requestId); throw error; }
      }
      respond(response, 404, { error: "not found" }, requestId);
    } catch {
      respond(response, 400, { error: "invalid request" }, requestId);
    }
  });
}

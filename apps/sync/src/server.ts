import { createServer, type Server } from "node:http";
import { WebSocketServer, type WebSocket } from "ws";
import { GuestSessionRegistry } from "@vulcan/domain";
import type { BoardStream } from "./index.js";

const MAX_SOCKET_QUEUE_BYTES = 5 * 1024 * 1024;
export function sendBounded(socket: Pick<WebSocket, "send" | "close"> & { bufferedAmount: number }, message: string, channel: "ops" | "presence"): boolean {
  if (socket.bufferedAmount + Buffer.byteLength(message) > MAX_SOCKET_QUEUE_BYTES) {
    if (channel === "presence") return false;
    socket.close(1013, "backpressure");
    return false;
  }
  socket.send(message);
  return true;
}

export function createSyncServer(registry: GuestSessionRegistry, stream: BoardStream): Server {
  const server = createServer((_request, response) => { response.statusCode = 404; response.end(); });
  const wss = new WebSocketServer({ server });
  const peers = new Map<string, Set<WebSocket>>();
  const operations = new Map<string, Map<string, { payload: string; sequence: number }>>();
  const boardTails = new Map<string, Promise<void>>();
  wss.on("connection", (socket: WebSocket, request) => {
    const url = new URL(request.url || "/", "http://localhost");
    const boardId = url.pathname.match(/^\/boards\/([^/]+)$/)?.[1] || "";
    const capability = url.searchParams.get("capability") || "";
    if (!registry.authorize(capability, boardId, "edit")) { socket.close(1008, "unauthorized"); return; }
    const boardPeers = peers.get(boardId) ?? new Set<WebSocket>();
    boardPeers.add(socket);
    peers.set(boardId, boardPeers);
    socket.on("close", () => { boardPeers.delete(socket); if (boardPeers.size === 0) peers.delete(boardId); });
    const afterParam = url.searchParams.get("after") || "0";
    const after = /^\d+(?:-\d+)?$/.test(afterParam) ? (afterParam.includes("-") ? afterParam : Number(afterParam)) : 0;
    if (after === 0 || typeof after === "number" || typeof after === "string") {
      void stream.replay(boardId, after).then((events) => {
        for (const event of events) {
          if (socket.readyState !== socket.OPEN) break;
          try {
            const operation = JSON.parse(event.data.toString()) as { operationId?: string; payload?: unknown };
            sendBounded(socket, JSON.stringify({ type: "op", sequence: event.id, operationId: operation.operationId, payload: operation.payload }), "ops");
          } catch { sendBounded(socket, JSON.stringify({ type: "error", code: "corrupt_replay" }), "ops"); }
        }
      }).catch(() => { if (socket.readyState === socket.OPEN) sendBounded(socket, JSON.stringify({ type: "error", code: "replay_unavailable" }), "ops"); });
    }
    socket.on("message", (raw) => {
      const processMessage = async (): Promise<void> => {
      try {
        const input = JSON.parse(raw.toString()) as { type?: string; operationId?: string; payload?: unknown };
        if (input.type !== "op" || !input.operationId) { sendBounded(socket, JSON.stringify({ type: "error", code: "invalid_operation" }), "ops"); return; }
        const boardOperations = operations.get(boardId) ?? new Map<string, { payload: string; sequence: number }>();
        operations.set(boardId, boardOperations);
        const payload = JSON.stringify(input.payload);
        const prior = boardOperations.get(input.operationId);
        const persisted = prior ? undefined : await stream.findOperation(boardId, input.operationId);
        const existing = prior ?? (persisted ? { payload: JSON.stringify((JSON.parse(persisted.data.toString()) as { payload?: unknown }).payload), sequence: persisted.id } : undefined);
        if (existing) {
          if (existing.payload !== payload) { sendBounded(socket, JSON.stringify({ type: "error", code: "idempotency_conflict" }), "ops"); return; }
          boardOperations.set(input.operationId, existing);
          sendBounded(socket, JSON.stringify({ type: "ack", sequence: existing.sequence, operationId: input.operationId }), "ops");
          return;
        }
        if (!registry.consumeWrite(capability)) { sendBounded(socket, JSON.stringify({ type: "error", code: "quota_exceeded" }), "ops"); return; }
        const event = await stream.append(boardId, Buffer.from(JSON.stringify({ operationId: input.operationId, payload: input.payload })));
        boardOperations.set(input.operationId, { payload, sequence: event.id });
        sendBounded(socket, JSON.stringify({ type: "ack", sequence: event.id, operationId: input.operationId }), "ops");
        const message = JSON.stringify({ type: "op", sequence: event.id, operationId: input.operationId, payload: input.payload });
        for (const peer of boardPeers) if (peer !== socket && peer.readyState === peer.OPEN) sendBounded(peer, message, "ops");
      } catch { sendBounded(socket, JSON.stringify({ type: "error", code: "invalid_message" }), "ops"); }
      };
      const previous = boardTails.get(boardId) ?? Promise.resolve();
      const current = previous.then(processMessage, processMessage);
      boardTails.set(boardId, current);
      void current.finally(() => { if (boardTails.get(boardId) === current) boardTails.delete(boardId); }).catch(() => undefined);
    });
  });
  return server;
}

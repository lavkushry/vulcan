import { createServer, type Server } from "node:http";
import { WebSocketServer, type WebSocket } from "ws";
import { GuestSessionRegistry } from "@vulcan/domain";
import type { BoardStream } from "./index.js";

export function createSyncServer(registry: GuestSessionRegistry, stream: BoardStream): Server {
  const server = createServer((_request, response) => { response.statusCode = 404; response.end(); });
  const wss = new WebSocketServer({ server });
  const peers = new Map<string, Set<WebSocket>>();
  const operations = new Map<string, Map<string, { payload: string; sequence: number }>>();
  wss.on("connection", (socket: WebSocket, request) => {
    const url = new URL(request.url || "/", "http://localhost");
    const boardId = url.pathname.match(/^\/boards\/([^/]+)$/)?.[1] || "";
    const capability = url.searchParams.get("capability") || "";
    if (!registry.authorize(capability, boardId, "edit")) { socket.close(1008, "unauthorized"); return; }
    const boardPeers = peers.get(boardId) ?? new Set<WebSocket>();
    boardPeers.add(socket);
    peers.set(boardId, boardPeers);
    socket.on("close", () => { boardPeers.delete(socket); if (boardPeers.size === 0) peers.delete(boardId); });
    const after = Number(url.searchParams.get("after") || 0);
    if (Number.isInteger(after) && after >= 0) {
      void stream.replay(boardId, after).then((events) => {
        for (const event of events) {
          if (socket.readyState !== socket.OPEN) break;
          try {
            const operation = JSON.parse(event.data.toString()) as { operationId?: string; payload?: unknown };
            socket.send(JSON.stringify({ type: "op", sequence: event.id, operationId: operation.operationId, payload: operation.payload }));
          } catch { socket.send(JSON.stringify({ type: "error", code: "corrupt_replay" })); }
        }
      });
    }
    socket.on("message", async (raw) => {
      try {
        const input = JSON.parse(raw.toString()) as { type?: string; operationId?: string; payload?: unknown };
        if (input.type !== "op" || !input.operationId) { socket.send(JSON.stringify({ type: "error", code: "invalid_operation" })); return; }
        const boardOperations = operations.get(boardId) ?? new Map<string, { payload: string; sequence: number }>();
        operations.set(boardId, boardOperations);
        const payload = JSON.stringify(input.payload);
        const prior = boardOperations.get(input.operationId);
        const persisted = prior ? undefined : await stream.findOperation(boardId, input.operationId);
        const existing = prior ?? (persisted ? { payload: JSON.stringify((JSON.parse(persisted.data.toString()) as { payload?: unknown }).payload), sequence: persisted.id } : undefined);
        if (existing) {
          if (existing.payload !== payload) { socket.send(JSON.stringify({ type: "error", code: "idempotency_conflict" })); return; }
          boardOperations.set(input.operationId, existing);
          socket.send(JSON.stringify({ type: "ack", sequence: existing.sequence, operationId: input.operationId }));
          return;
        }
        if (!registry.consumeWrite(capability)) { socket.send(JSON.stringify({ type: "error", code: "quota_exceeded" })); return; }
        const event = await stream.append(boardId, Buffer.from(JSON.stringify({ operationId: input.operationId, payload: input.payload })));
        boardOperations.set(input.operationId, { payload, sequence: event.id });
        socket.send(JSON.stringify({ type: "ack", sequence: event.id, operationId: input.operationId }));
        const message = JSON.stringify({ type: "op", sequence: event.id, operationId: input.operationId, payload: input.payload });
        for (const peer of boardPeers) if (peer !== socket && peer.readyState === peer.OPEN) peer.send(message);
      } catch { socket.send(JSON.stringify({ type: "error", code: "invalid_message" })); }
    });
  });
  return server;
}

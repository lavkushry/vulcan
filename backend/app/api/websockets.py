"""
Project Vulcan: WebSocket Dual-Write Ring Buffer Manager
Author: Alex Xu (Distributed Systems Lead)
Solves the Late-Joiner problem by buffering stdout in a ring buffer and replaying to newly joined clients.
"""
import asyncio
import json
import logging
import threading
from datetime import datetime, timezone
from typing import Dict, List, Set
from fastapi import WebSocket

logger = logging.getLogger("vulcan.ws")


class WebSocketLogHub:
    """
    Manages real-time log streaming to xterm.js clients.
    Features:
    - In-memory ring buffer (up to 10,000 lines per job)
    - Late-joiner historical replay from last_seq
    - Thread-safe broadcast from worker threads to async WebSockets
    """

    def __init__(self, max_buffer_lines: int = 10000):
        self.max_buffer_lines = max_buffer_lines
        self.buffers: Dict[str, List[Dict]] = {}
        self.connections: Dict[str, Set[WebSocket]] = {}
        self._lock = threading.Lock()
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._redis: Optional[Any] = None

    def set_event_loop(self, loop: asyncio.AbstractEventLoop):
        self._loop = loop

    def set_redis_client(self, redis_client: Any):
        """Enable Redis Pub/Sub backplane for distributed multi-worker broadcast."""
        self._redis = redis_client

    def publish(self, correlation_id: str, type_: str, data: Any):
        """
        Publishes structured WebSocket events (stdout, status, diagnostic).
        Thread-safe. Pushes to ring buffer and broadcasts to active WebSockets.
        """
        with self._lock:
            if correlation_id not in self.buffers:
                self.buffers[correlation_id] = []

            buf = self.buffers[correlation_id]
            seq = len(buf) + 1
            payload_data = data if isinstance(data, dict) else {"data": str(data)}
            entry = {
                "seq": seq,
                "type": type_,
                "event": type_,
                "job_id": correlation_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "data": payload_data,
            }
            buf.append(entry)
            if len(buf) > self.max_buffer_lines:
                buf.pop(0)

            active_sockets = list(self.connections.get(correlation_id, set()))

        # Broadcast to local connected WebSockets
        if active_sockets:
            loop = self._loop
            if not loop or not loop.is_running():
                try:
                    loop = asyncio.get_running_loop()
                except RuntimeError:
                    loop = None
            if loop and loop.is_running():
                asyncio.run_coroutine_threadsafe(
                    self._broadcast_to_sockets(active_sockets, entry),
                    loop
                )

        # Broadcast to Redis Pub/Sub backplane for multi-worker topology
        if self._redis:
            try:
                self._redis.publish(f"vulcan:ws:{correlation_id}", json.dumps(entry))
            except Exception as e:
                logger.debug(f"Redis pub/sub publish failed: {e}")

    def emit_log(self, correlation_id: str, line: str, stream: str = "stdout"):
        """
        Emitted by worker runners. Thread-safe.
        Pushes to ring buffer and schedules broadcast to active WebSockets.
        """
        self.publish(correlation_id, "stdout", {
            "line": line,
            "data": line + "\r\n",
            "stream": stream,
        })

    async def _broadcast_to_sockets(self, sockets: List[WebSocket], message: Dict):
        payload = json.dumps(message)
        for ws in sockets:
            try:
                await ws.send_text(payload)
            except Exception:
                pass

    async def register(self, websocket: WebSocket, correlation_id: str, last_seq: int = 0):
        """
        Accepts WebSocket connection, replays past logs, and adds socket to active set.
        """
        await websocket.accept()

        with self._lock:
            if correlation_id not in self.connections:
                self.connections[correlation_id] = set()
            self.connections[correlation_id].add(websocket)
            history = list(self.buffers.get(correlation_id, []))

        # Replay missed messages for late joiners
        for item in history:
            if item["seq"] > last_seq:
                try:
                    await websocket.send_text(json.dumps(item))
                except Exception:
                    break

    def unregister(self, websocket: WebSocket, correlation_id: str):
        with self._lock:
            if correlation_id in self.connections:
                self.connections[correlation_id].discard(websocket)


ws_hub = WebSocketLogHub()

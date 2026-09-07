"""
Project Vulcan: WebSocket Dual-Write Ring Buffer & Redis Pub/Sub Fanout Manager (Milestone B)
Author: Alex Xu (Distributed Systems Lead)
Solves the Late-Joiner problem and provides real-time cross-worker log streaming via Redis Pub/Sub.
"""
import asyncio
import json
import logging
import os
import threading
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set
from fastapi import WebSocket

logger = logging.getLogger("vulcan.ws")


class WebSocketLogHub:
    """
    Manages real-time log streaming to xterm.js clients across multi-worker uvicorn topology.
    Features:
    - Local in-memory ring buffer (up to 10,000 lines per job)
    - Redis list backing for distributed late-joiner historical replay
    - Redis Pub/Sub cross-worker event fanout
    - Thread-safe broadcast from worker threads to async WebSockets
    """

    def __init__(self, max_buffer_lines: int = 10000):
        self.max_buffer_lines = max_buffer_lines
        self.buffers: Dict[str, List[Dict]] = {}
        self.connections: Dict[str, Set[WebSocket]] = {}
        self._lock = threading.Lock()
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._redis: Optional[Any] = None
        self.worker_id = f"worker-{os.getpid()}-{uuid.uuid4().hex[:6]}"
        self._stop_subscriber = threading.Event()
        self._subscriber_thread: Optional[threading.Thread] = None

    def set_event_loop(self, loop: asyncio.AbstractEventLoop):
        self._loop = loop

    def set_redis_client(self, redis_client: Any):
        """Enable Redis Pub/Sub backplane and start background listener thread."""
        self._redis = redis_client
        if redis_client and (self._subscriber_thread is None or not self._subscriber_thread.is_alive()):
            self._stop_subscriber.clear()
            self._subscriber_thread = threading.Thread(
                target=self._redis_subscriber_loop,
                name=f"ws-redis-sub-{self.worker_id}",
                daemon=True
            )
            self._subscriber_thread.start()
            logger.info("Started Redis Pub/Sub event subscriber thread on %s", self.worker_id)

    def _redis_subscriber_loop(self):
        """Background thread listening for events published by peer workers."""
        if not self._redis:
            return

        try:
            pubsub = self._redis.pubsub()
            pubsub.subscribe("vulcan:ws:events")
            logger.info("Subscribed to Redis channel 'vulcan:ws:events'")
        except Exception as e:
            logger.warning("Could not subscribe to Redis pubsub: %s", e)
            return

        while not self._stop_subscriber.is_set():
            try:
                msg = pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if msg and msg.get("type") == "message":
                    raw_data = msg.get("data")
                    if isinstance(raw_data, bytes):
                        raw_data = raw_data.decode("utf-8")
                    entry = json.loads(raw_data)
                    # If event originated from a different worker, fan out locally
                    if entry.get("worker_id") != self.worker_id:
                        self._handle_remote_event(entry)
            except Exception as e:
                if not self._stop_subscriber.is_set():
                    logger.debug("Redis pubsub listener exception: %s", e)
                    time.sleep(0.5)

        try:
            pubsub.close()
        except Exception:
            pass

    def _handle_remote_event(self, entry: Dict[str, Any]):
        """Dispatches an event from a peer worker to locally connected WebSockets."""
        correlation_id = entry.get("job_id")
        if not correlation_id:
            return

        with self._lock:
            if correlation_id not in self.buffers:
                self.buffers[correlation_id] = []
            buf = self.buffers[correlation_id]
            buf.append(entry)
            if len(buf) > self.max_buffer_lines:
                buf.pop(0)

            active_sockets = list(self.connections.get(correlation_id, set()))

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

    def publish(self, correlation_id: str, type_: str, data: Any):
        """
        Publishes structured WebSocket events (stdout, status, diagnostic).
        Thread-safe. Pushes to ring buffer and broadcasts to active WebSockets.
        Funnels to Redis Pub/Sub for cross-worker fanout.
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
                "worker_id": self.worker_id,
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

        # Broadcast to Redis Pub/Sub and persist in Redis list for multi-worker topology
        if self._redis:
            try:
                serialized = json.dumps(entry)
                # 1. Pub/Sub event for active listening workers
                self._redis.publish("vulcan:ws:events", serialized)
                # 2. Redis list for late joiners
                list_key = f"vulcan:logs:{correlation_id}"
                self._redis.rpush(list_key, serialized)
                self._redis.ltrim(list_key, -self.max_buffer_lines, -1)
                # Expire raw log buffers after 24 hours
                self._redis.expire(list_key, 86400)
            except Exception as e:
                logger.debug("Redis pub/sub publish failed: %s", e)

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
        Fetches historical replay from Redis if available, ensuring cross-worker replay.
        """
        await websocket.accept()

        history: List[Dict[str, Any]] = []
        if self._redis:
            try:
                raw_entries = self._redis.lrange(f"vulcan:logs:{correlation_id}", 0, -1)
                if raw_entries:
                    for raw in raw_entries:
                        if isinstance(raw, bytes):
                            raw = raw.decode("utf-8")
                        history.append(json.loads(raw))
            except Exception as e:
                logger.debug("Error fetching historical logs from Redis: %s", e)

        with self._lock:
            if correlation_id not in self.connections:
                self.connections[correlation_id] = set()
            self.connections[correlation_id].add(websocket)
            if not history:
                history = list(self.buffers.get(correlation_id, []))

        # Replay missed messages for late joiners
        for item in history:
            if item.get("seq", 0) > last_seq:
                try:
                    await websocket.send_text(json.dumps(item))
                except Exception:
                    break

    def unregister(self, websocket: WebSocket, correlation_id: str):
        with self._lock:
            if correlation_id in self.connections:
                self.connections[correlation_id].discard(websocket)

    def stop(self):
        """Clean shutdown of background subscriber."""
        self._stop_subscriber.set()
        if self._subscriber_thread and self._subscriber_thread.is_alive():
            self._subscriber_thread.join(timeout=2.0)


ws_hub = WebSocketLogHub()

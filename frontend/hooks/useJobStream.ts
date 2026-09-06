"use client";
import { useEffect, useState } from "react";
import type { WsEvent } from "@/lib/types";
import { getWsBaseUrl } from "@/lib/env";

export function useJobStream(jobId: string | null) {
  const [events, setEvents] = useState<WsEvent[]>([]);
  const [live, setLive] = useState(false);
  const [latestHeartbeat, setLatestHeartbeat] = useState<WsEvent | null>(null);

  useEffect(() => {
    if (!jobId) return;
    setEvents([]);
    setLive(false);
    setLatestHeartbeat(null);
    let ws: WebSocket | null = null;
    let closed = false;
    let lastSeq = 0;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let retryCount = 0;

    // RAF batching queue (UI-05: 60 FPS frame budget)
    let queue: WsEvent[] = [];
    let rafId: number | null = null;

    const flushQueue = () => {
      if (queue.length > 0) {
        const batch = queue;
        queue = [];
        setEvents((prev) => {
          // Cap at 5,000 lines to guarantee O(1) DOM memory ceiling
          const next = [...prev, ...batch];
          return next.length > 5000 ? next.slice(next.length - 5000) : next;
        });
      }
      rafId = null;
    };

    const connect = () => {
      const token = (typeof window !== "undefined" ? window.localStorage.getItem("vulcan_api_token") : null) || process.env.NEXT_PUBLIC_VULCAN_API_TOKEN || "";
      const tokenParam = token ? `&token=${encodeURIComponent(token)}` : "";
      // last_seq => server replays buffered events first, then streams live
      ws = new WebSocket(`${getWsBaseUrl()}/api/v1/ws/jobs/${jobId}?last_seq=${lastSeq}${tokenParam}`);
      ws.onopen = () => {
        setLive(true);
        retryCount = 0;
      };
      ws.onmessage = (msg) => {
        try {
          const evt: WsEvent = JSON.parse(msg.data as string);
          if (evt.seq <= lastSeq) return; // dedupe
          lastSeq = evt.seq;

          if (evt.type === "lock_heartbeat") {
            setLatestHeartbeat(evt);
          }

          queue.push(evt);
          if (rafId === null) {
            rafId = requestAnimationFrame(flushQueue);
          }
        } catch { /* ignore corrupted frame */ }
      };
      ws.onclose = (event: CloseEvent) => {
        setLive(false);
        if (!closed) {
          // If unauthenticated (4401), fail closed and do not spam reconnect attempts
          if (event.code === 4401) {
            console.error(`[Vulcan WS] Connection closed with code 4401: Unauthorized API token.`);
            return;
          }
          // Exponential backoff with full jitter to eliminate thundering-herd storms
          retryCount++;
          const baseDelay = Math.min(1000 * Math.pow(1.5, retryCount), 10000);
          const jitter = Math.random() * 500;
          timer = setTimeout(connect, baseDelay + jitter);
        }
      };
      ws.onerror = () => ws?.close();
    };
    connect();

    return () => {
      closed = true;
      if (timer) clearTimeout(timer);
      if (rafId !== null) cancelAnimationFrame(rafId);
      ws?.close();
    };
  }, [jobId]);

  return { events, live, latestHeartbeat };
}

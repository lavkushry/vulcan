"use client";
import { useEffect, useState } from "react";
import type { WsEvent } from "@/lib/types";

const WS_BASE = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(/^http/, "ws");

export function useJobStream(jobId: string | null) {
  const [events, setEvents] = useState<WsEvent[]>([]);
  const [live, setLive] = useState(false);

  useEffect(() => {
    if (!jobId) return;
    setEvents([]);
    setLive(false);
    let ws: WebSocket | null = null;
    let closed = false;
    let lastSeq = 0;
    let timer: ReturnType<typeof setTimeout> | undefined;

    const connect = () => {
      // last_seq => server replays buffered events first, then streams live
      ws = new WebSocket(`${WS_BASE}/api/v1/ws/jobs/${jobId}?last_seq=${lastSeq}`);
      ws.onopen = () => setLive(true);
      ws.onmessage = (msg) => {
        const evt: WsEvent = JSON.parse(msg.data as string);
        if (evt.seq <= lastSeq) return; // dedupe
        lastSeq = evt.seq;
        setEvents((prev) => [...prev, evt]);
      };
      ws.onclose = () => {
        setLive(false);
        if (!closed) timer = setTimeout(connect, 1500); // reconnect, resume from last_seq
      };
      ws.onerror = () => ws?.close();
    };
    connect();

    return () => { closed = true; if (timer) clearTimeout(timer); ws?.close(); };
  }, [jobId]);

  return { events, live };
}

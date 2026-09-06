"use client";
import { useEffect, useRef } from "react";
import type { WsEvent } from "@/lib/types";

export function Terminal({ events, live }: { events: WsEvent[]; live: boolean }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (ref.current) ref.current.scrollTop = ref.current.scrollHeight;
  }, [events]);

  return (
    <div className="flex h-full min-h-0 flex-col rounded-lg border border-slate-800 bg-[#05070B]">
      <div className="flex items-center gap-2 border-b border-slate-800 px-3 py-1.5 text-[10px] uppercase tracking-widest text-slate-500">
        <span className={`h-1.5 w-1.5 rounded-full ${live ? "animate-pulse bg-emerald-400" : "bg-slate-600"}`} />
        {live ? "live stream" : "buffered replay"}
      </div>
      <div ref={ref} className="flex-1 overflow-y-auto p-3 font-mono text-xs leading-5 text-slate-300">
        {events.map((e) => {
          if (e.type === "stdout") return <div key={e.seq} className="whitespace-pre-wrap">{e.data?.line ?? (typeof e.data === "string" ? e.data : e.data?.data)}</div>;
          if (e.type === "status") return <div key={e.seq} className="my-1 text-cyan-400/80">── {e.data?.status}{e.data?.message ? ` · ${e.data.message}` : ""} ──</div>;
          if (e.type === "diagnostic") return <div key={e.seq} className="my-1 whitespace-pre-wrap text-rose-400">⚠ {e.data?.root_cause}</div>;
          return null;
        })}
      </div>
    </div>
  );
}

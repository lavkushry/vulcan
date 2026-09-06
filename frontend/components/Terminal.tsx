"use client";
import { useEffect, useRef, useState, useMemo } from "react";
import type { WsEvent } from "@/lib/types";
import { TerminalActionBar } from "./TerminalActionBar";

export function Terminal({ events, live }: { events: WsEvent[]; live: boolean }) {
  const ref = useRef<HTMLDivElement>(null);
  const [clearedSeq, setClearedSeq] = useState<number>(0);
  const [isAutoscrollLocked, setIsAutoscrollLocked] = useState<boolean>(false);
  const [searchQuery, setSearchQuery] = useState<string>("");

  // Visible events after clear
  const visibleEvents = useMemo(() => {
    return events.filter((e) => e.seq > clearedSeq);
  }, [events, clearedSeq]);

  // Autoscroll effect
  useEffect(() => {
    if (!isAutoscrollLocked && ref.current) {
      ref.current.scrollTop = ref.current.scrollHeight;
    }
  }, [visibleEvents, isAutoscrollLocked]);

  // Copy raw clean stdout without ANSI escape codes
  const handleCopyStdout = () => {
    const rawLines = visibleEvents
      .filter((e) => e.type === "stdout")
      .map((e) => {
        const raw = e.data?.line ?? (typeof e.data === "string" ? e.data : e.data?.data) ?? "";
        // Strip ANSI escape codes
        return raw.replace(/[\u001b\u009b][[()#;?]*(?:[0-9]{1,4}(?:;[0-9]{0,4})*)?[0-9A-ORZcf-nqry=><]/g, "");
      })
      .join("\n");

    navigator.clipboard.writeText(rawLines || "No output lines to copy.");
  };

  const handleClear = () => {
    if (events.length > 0) {
      setClearedSeq(events[events.length - 1].seq);
    }
  };

  // Filtered lines based on search query
  const filteredEvents = useMemo(() => {
    if (!searchQuery.trim()) return visibleEvents;
    const q = searchQuery.toLowerCase();
    return visibleEvents.filter((e) => {
      const line = (e.data?.line ?? (typeof e.data === "string" ? e.data : e.data?.data) ?? "").toLowerCase();
      const status = (e.data?.status ?? "").toLowerCase();
      const diag = (e.data?.root_cause ?? "").toLowerCase();
      return line.includes(q) || status.includes(q) || diag.includes(q);
    });
  }, [visibleEvents, searchQuery]);

  return (
    <div className="flex h-full min-h-0 flex-col rounded-lg border border-slate-800 bg-[#05070B] overflow-hidden">
      {/* Live Terminal Action Bar */}
      <TerminalActionBar
        onClear={handleClear}
        onCopyStdout={handleCopyStdout}
        isAutoscrollLocked={isAutoscrollLocked}
        onToggleAutoscroll={() => setIsAutoscrollLocked((prev) => !prev)}
        bufferLines={visibleEvents.length}
        searchQuery={searchQuery}
        onSearchChange={setSearchQuery}
      />

      {/* Terminal Output */}
      <div ref={ref} className="flex-1 overflow-y-auto p-3 font-mono text-xs leading-5 text-slate-300">
        {filteredEvents.length === 0 ? (
          <div className="text-slate-600 italic py-4 text-center">
            {searchQuery ? `No log lines matching "${searchQuery}"` : "Awaiting stdout stream…"}
          </div>
        ) : (
          filteredEvents.map((e) => {
            if (e.type === "stdout") {
              const text = e.data?.line ?? (typeof e.data === "string" ? e.data : e.data?.data) ?? "";
              return (
                <div key={e.seq} className="whitespace-pre-wrap hover:bg-slate-900/40 px-1 rounded transition-colors">
                  {text}
                </div>
              );
            }
            if (e.type === "status") {
              return (
                <div key={e.seq} className="my-1.5 px-2 py-0.5 rounded bg-cyan-950/40 border border-cyan-500/20 text-cyan-300 font-semibold text-[11px]">
                  ── {e.data?.status}{e.data?.message ? ` · ${e.data.message}` : ""} ──
                </div>
              );
            }
            if (e.type === "diagnostic") {
              return (
                <div key={e.seq} className="my-2 p-2 rounded bg-rose-950/40 border border-rose-500/30 whitespace-pre-wrap text-rose-300 font-bold">
                  ⚠ Root-Cause Diagnostic: {e.data?.root_cause}
                </div>
              );
            }
            return null;
          })
        )}
      </div>
    </div>
  );
}

export default Terminal;

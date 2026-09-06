"use client";
import { useEffect, useRef, useState, useMemo } from "react";
import type { WsEvent } from "@/lib/types";
import { TerminalActionBar } from "./TerminalActionBar";

export function Terminal({ events, live }: { events: WsEvent[]; live: boolean }) {
  const terminalRef = useRef<HTMLDivElement>(null);
  const xtermInstance = useRef<any>(null);
  const fitAddonRef = useRef<any>(null);
  const lastWrittenSeq = useRef<number>(0);

  const [clearedSeq, setClearedSeq] = useState<number>(0);
  const [isAutoscrollLocked, setIsAutoscrollLocked] = useState<boolean>(false);
  const [searchQuery, setSearchQuery] = useState<string>(0 ? "" : "");
  const [xtermLoaded, setXtermLoaded] = useState<boolean>(false);

  // Visible events after clear
  const visibleEvents = useMemo(() => {
    return events.filter((e) => e.seq > clearedSeq);
  }, [events, clearedSeq]);

  // Mount and configure xterm.js instance with WebGL and Fit addons
  useEffect(() => {
    if (typeof window === "undefined" || !terminalRef.current) return;
    let isMounted = true;

    async function initXterm() {
      try {
        const { Terminal: XTerminal } = await import("@xterm/xterm");
        const { FitAddon } = await import("@xterm/addon-fit");
        let WebglAddon: any = null;
        try {
          const webglModule = await import("@xterm/addon-webgl");
          WebglAddon = webglModule.WebglAddon;
        } catch {
          // WebGL addon optional fallback
        }

        if (!isMounted || !terminalRef.current) return;

        const term = new XTerminal({
          theme: {
            background: "#05070B",
            foreground: "#CBD5E1",
            cursor: "#06B6D4",
            selectionBackground: "#0891B240",
            black: "#05070B",
            red: "#F43F5E",
            green: "#10B981",
            yellow: "#F59E0B",
            blue: "#3B82F6",
            magenta: "#EC4899",
            cyan: "#06B6D4",
            white: "#F8FAFC",
          },
          fontFamily: '"JetBrains Mono", Menlo, Monaco, "Courier New", monospace',
          fontSize: 12,
          lineHeight: 1.4,
          cursorBlink: live,
          disableStdin: true,
          convertEol: true,
        });

        const fitAddon = new FitAddon();
        term.loadAddon(fitAddon);

        term.open(terminalRef.current);

        if (WebglAddon) {
          try {
            const webgl = new WebglAddon();
            webgl.onContextLoss(() => webgl.dispose());
            term.loadAddon(webgl);
          } catch {
            // WebGL canvas context unavailable; software canvas used
          }
        }

        fitAddon.fit();
        xtermInstance.current = term;
        fitAddonRef.current = fitAddon;

        // Detect user scroll-up to pause autoscroll (UI-18)
        term.onScroll((newPosition: number) => {
          const buffer = term.buffer.active;
          const isAtBottom = newPosition >= buffer.baseY;
          setIsAutoscrollLocked(!isAtBottom);
        });

        // Resize observer for responsive layout
        const resizeObserver = new ResizeObserver(() => {
          try {
            fitAddon.fit();
          } catch {
            // Ignore resize exceptions during DOM detach
          }
        });
        resizeObserver.observe(terminalRef.current);

        setXtermLoaded(true);

        return () => {
          resizeObserver.disconnect();
          term.dispose();
        };
      } catch (err) {
        console.warn("xterm.js initialization fallback to standard render:", err);
      }
    }

    const cleanupPromise = initXterm();

    return () => {
      isMounted = false;
      cleanupPromise.then((cleanup) => cleanup && cleanup());
    };
  }, [live]);

  // Feed new incoming events into xterm instance
  useEffect(() => {
    const term = xtermInstance.current;
    if (!term || !xtermLoaded) return;

    for (const e of visibleEvents) {
      if (e.seq > lastWrittenSeq.current) {
        lastWrittenSeq.current = e.seq;
        if (e.type === "stdout") {
          const line = e.data?.line ?? (typeof e.data === "string" ? e.data : e.data?.data) ?? "";
          term.writeln(line);
        } else if (e.type === "status") {
          term.writeln(`\x1b[1;36m── ${e.data?.status}${e.data?.message ? ` · ${e.data.message}` : ""} ──\x1b[0m`);
        } else if (e.type === "diagnostic") {
          term.writeln(`\x1b[1;31m⚠ Root-Cause Diagnostic: ${e.data?.root_cause}\x1b[0m`);
        }
      }
    }

    if (!isAutoscrollLocked) {
      term.scrollToBottom();
    }
  }, [visibleEvents, xtermLoaded, isAutoscrollLocked]);

  // Clear handler
  const handleClear = () => {
    if (events.length > 0) {
      setClearedSeq(events[events.length - 1].seq);
    }
    if (xtermInstance.current) {
      xtermInstance.current.clear();
      lastWrittenSeq.current = events.length > 0 ? events[events.length - 1].seq : 0;
    }
  };

  // Copy raw stdout without ANSI escape codes
  const handleCopyStdout = () => {
    const rawLines = visibleEvents
      .filter((e) => e.type === "stdout")
      .map((e) => {
        const raw = e.data?.line ?? (typeof e.data === "string" ? e.data : e.data?.data) ?? "";
        return raw.replace(/[\u001b\u009b][[()#;?]*(?:[0-9]{1,4}(?:;[0-9]{0,4})*)?[0-9A-ORZcf-nqry=><]/g, "");
      })
      .join("\n");

    navigator.clipboard.writeText(rawLines || "No output lines to copy.");
  };

  return (
    <div className="relative flex h-full min-h-0 flex-col rounded-lg border border-slate-800 bg-[#05070B] overflow-hidden">
      {/* Live Terminal Action Bar */}
      <TerminalActionBar
        onClear={handleClear}
        onCopyStdout={handleCopyStdout}
        isAutoscrollLocked={isAutoscrollLocked}
        onToggleAutoscroll={() => {
          setIsAutoscrollLocked((prev) => {
            const next = !prev;
            if (!next && xtermInstance.current) {
              xtermInstance.current.scrollToBottom();
            }
            return next;
          });
        }}
        bufferLines={visibleEvents.length}
        searchQuery={searchQuery}
        onSearchChange={setSearchQuery}
      />

      {/* xterm.js Canvas Host */}
      <div className="flex-1 relative w-full h-full min-h-[300px] overflow-hidden p-2">
        <div ref={terminalRef} className="w-full h-full" />
      </div>

      {/* Floating Scroll Paused Pill (UI-18) */}
      {isAutoscrollLocked && (
        <button
          type="button"
          onClick={() => {
            setIsAutoscrollLocked(false);
            if (xtermInstance.current) {
              xtermInstance.current.scrollToBottom();
            }
          }}
          className="absolute bottom-3 right-4 px-2.5 py-1 rounded bg-amber-500/20 border border-amber-500/40 text-amber-300 hover:bg-amber-500/30 text-xs font-mono font-bold shadow-lg flex items-center gap-1.5 animate-bounce z-10 transition-colors"
        >
          <span>↓ SCROLL PAUSED (Resume tail)</span>
        </button>
      )}
    </div>
  );
}

export default Terminal;

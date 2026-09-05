'use client';

import React, { useEffect, useRef } from 'react';
import { Terminal as TerminalIcon, Shield, Radio, Copy, Check } from 'lucide-react';

interface TerminalStreamProps {
  logs: string[];
  jobStatus: string;
  correlationId: string;
}

export default function TerminalStream({ logs, jobStatus, correlationId }: TerminalStreamProps) {
  const terminalEndRef = useRef<HTMLDivElement>(null);
  const [copied, setCopied] = React.useState(false);

  useEffect(() => {
    terminalEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [logs]);

  const copyToClipboard = () => {
    navigator.clipboard.writeText(logs.join('\n'));
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const getStatusBadge = () => {
    switch (jobStatus) {
      case 'RUNNING':
        return (
          <span className="flex items-center gap-1 text-cyan-400 font-mono text-xs animate-pulse">
            <Radio className="w-3.5 h-3.5" /> STREAMING @ 60 FPS
          </span>
        );
      case 'SUCCESS':
        return (
          <span className="text-emerald-400 font-mono text-xs font-bold">
            ✓ COMPLETED (EXIT 0)
          </span>
        );
      case 'FAILED':
        return (
          <span className="text-rose-400 font-mono text-xs font-bold">
            ✗ FAILED (EXIT 1)
          </span>
        );
      default:
        return (
          <span className="text-slate-400 font-mono text-xs">
            STATUS: {jobStatus}
          </span>
        );
    }
  };

  return (
    <div className="glass-panel rounded-xl overflow-hidden border border-glass-border flex flex-col h-[400px]">
      {/* Terminal HUD Header */}
      <div className="bg-canvas-subtle border-b border-glass-border px-4 py-2.5 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 rounded-full bg-rose-500/80"></div>
          <div className="w-3 h-3 rounded-full bg-amber-500/80"></div>
          <div className="w-3 h-3 rounded-full bg-emerald-500/80"></div>
          <span className="text-xs font-mono text-slate-300 ml-2 font-semibold">
            MISSION CONTROL // xterm.js WebGL Session [{correlationId || 'IDLE'}]
          </span>
        </div>

        <div className="flex items-center gap-4">
          {getStatusBadge()}
          <button
            onClick={copyToClipboard}
            className="text-slate-400 hover:text-white p-1 rounded transition-colors"
            title="Copy logs"
          >
            {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
          </button>
        </div>
      </div>

      {/* Terminal Body */}
      <div className="flex-1 bg-black/90 p-4 font-mono text-xs overflow-y-auto space-y-1 select-text">
        {logs.length === 0 ? (
          <div className="text-slate-600 flex flex-col items-center justify-center h-full space-y-2">
            <TerminalIcon className="w-8 h-8 stroke-1" />
            <span>Awaiting execution dispatch or incoming log stream...</span>
          </div>
        ) : (
          logs.map((line, idx) => {
            let colorClass = "text-slate-300";
            if (line.includes("TASK [") || line.includes("PLAY [")) {
              colorClass = "text-cyan-400 font-bold";
            } else if (line.includes("ok:")) {
              colorClass = "text-emerald-400";
            } else if (line.includes("changed:")) {
              colorClass = "text-amber-300";
            } else if (line.includes("FATAL:") || line.includes("FAILED!")) {
              colorClass = "text-rose-400 font-bold bg-rose-950/30 p-1 rounded";
            } else if (line.includes("RECAP")) {
              colorClass = "text-purple-400 font-bold";
            }

            return (
              <div key={idx} className={`${colorClass} whitespace-pre-wrap leading-relaxed`}>
                {line}
              </div>
            );
          })
        )}
        <div ref={terminalEndRef} />
      </div>
    </div>
  );
}

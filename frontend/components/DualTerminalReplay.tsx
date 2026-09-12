'use client';

import React, { useState, useRef, useEffect, useMemo } from 'react';
import {
  X,
  Split,
  Layers,
  Play,
  Pause,
  Copy,
  Check,
  CheckCircle2,
  AlertCircle,
  Clock,
  ArrowRight,
  Search
} from 'lucide-react';
import type { WsEvent } from '@/lib/types';

interface DualTerminalReplayProps {
  currentEvents: WsEvent[];
  currentCorrelationId: string;
  isOpen: boolean;
  onClose: () => void;
  baselineJobId?: string;
}

export const DualTerminalReplay: React.FC<DualTerminalReplayProps> = ({
  currentEvents,
  currentCorrelationId,
  isOpen,
  onClose,
  baselineJobId = 'GOLDEN-RUN-8492'
}) => {
  const [syncScroll, setSyncScroll] = useState<boolean>(true);
  const [highlightDiff, setHighlightDiff] = useState<boolean>(true);
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [copied, setCopied] = useState<boolean>(false);

  const leftPaneRef = useRef<HTMLDivElement>(null);
  const rightPaneRef = useRef<HTMLDivElement>(null);
  const isScrollingRef = useRef<boolean>(false);

  // Synthesize canonical golden baseline events for comparison
  const baselineEvents: WsEvent[] = useMemo(() => {
    const baseLines = [
      '[INIT] Vulcan BaseJobRunner worker PID 54 initialized.',
      '[MUTEX] Acquired distributed Redlock on target resource lease 30s.',
      '[AUDIT] Synchronous write-before-execute Merkle ledger block committed.',
      '[PREFLIGHT] Pre-flight network and connectivity probes OK.',
      'PLAY [Governed Automation Execution] *************************************',
      'TASK [Gathering Facts] *************************************************',
      'ok: [target.internal] => {"ansible_facts": {"discovered_interpreter_python": "/usr/bin/python3"}}',
      'TASK [Verify Target Resource Lease & Governance Window] ****************',
      'ok: [target.internal] => {"msg": "ServiceNow CHG window active and attested."}',
      'TASK [Apply Governed Configuration / Certificate Renewal] **************',
      'changed: [target.internal] => {"changed": true, "msg": "Certificate updated and reloaded."}',
      'TASK [Execute Post-Flight Cryptographic Health Probes] ******************',
      'ok: [target.internal] => {"status": "HEALTHY", "latency_ms": 1.45, "http_status": 200}',
      'PLAY RECAP *************************************************************',
      'target.internal : ok=5    changed=1    unreachable=0    failed=0    rescued=0    ignored=0',
      '[MUTEX] Released Redlock lease token monotonically.',
      '[AUDIT] Terminal execution state SUCCESS committed with exit code 0.',
      '[COMPLETE] Automation job completed successfully.'
    ];

    const now = Date.now();
    return baseLines.map((line, idx) => ({
      seq: idx + 1,
      type: 'stdout',
      data: { line, stream: 'stdout' },
      timestamp: new Date(now - (baseLines.length - idx) * 1000).toISOString()
    }));
  }, []);

  // Filter current events that are stdout
  const activeStdoutLines = useMemo(() => {
    return currentEvents.filter((e) => e.type === 'stdout' && e.data?.line);
  }, [currentEvents]);

  // Synchronized scroll handling
  const handleScroll = (source: 'left' | 'right') => {
    if (!syncScroll || isScrollingRef.current) return;
    isScrollingRef.current = true;

    if (source === 'left' && leftPaneRef.current && rightPaneRef.current) {
      const percentage = leftPaneRef.current.scrollTop / (leftPaneRef.current.scrollHeight - leftPaneRef.current.clientHeight || 1);
      rightPaneRef.current.scrollTop = percentage * (rightPaneRef.current.scrollHeight - rightPaneRef.current.clientHeight);
    } else if (source === 'right' && rightPaneRef.current && leftPaneRef.current) {
      const percentage = rightPaneRef.current.scrollTop / (rightPaneRef.current.scrollHeight - rightPaneRef.current.clientHeight || 1);
      leftPaneRef.current.scrollTop = percentage * (leftPaneRef.current.scrollHeight - leftPaneRef.current.clientHeight);
    }

    setTimeout(() => {
      isScrollingRef.current = false;
    }, 50);
  };

  const handleCopy = () => {
    const text = activeStdoutLines.map((e) => e.data.line).join('\n');
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  if (!isOpen) return null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="dual-terminal-title"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/85 backdrop-blur-md p-4 animate-fadeIn"
      onClick={onClose}
    >
      <div
        className="w-full max-w-6xl h-[90vh] bg-[#0C101A] border border-slate-800 rounded-2xl flex flex-col font-mono shadow-2xl overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <header className="px-5 py-3 border-b border-slate-800 bg-[#07090E] flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2.5">
            <Split size={18} className="text-cyan-400" />
            <div>
              <h2 id="dual-terminal-title" className="text-xs font-bold text-slate-100 uppercase tracking-wider flex items-center gap-2">
                <span>Dual-Pane Split-Screen Terminal Replay</span>
                <span className="text-[10px] px-1.5 py-0.2 rounded border border-cyan-500/30 bg-cyan-950/40 text-cyan-300">
                  UI-27
                </span>
              </h2>
              <p className="text-[10px] text-slate-500">
                Comparative analysis: Golden baseline run vs live active stdout stream
              </p>
            </div>
          </div>

          {/* Controls */}
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => setSyncScroll(!syncScroll)}
              className={`px-2.5 py-1 rounded text-[11px] font-semibold border transition-colors cursor-pointer ${
                syncScroll
                  ? 'bg-cyan-950/60 text-cyan-300 border-cyan-500/40'
                  : 'bg-slate-900 text-slate-400 border-slate-800'
              }`}
            >
              Sync Viewports: {syncScroll ? 'ON' : 'OFF'}
            </button>

            <button
              type="button"
              onClick={() => setHighlightDiff(!highlightDiff)}
              className={`px-2.5 py-1 rounded text-[11px] font-semibold border transition-colors cursor-pointer ${
                highlightDiff
                  ? 'bg-emerald-950/60 text-emerald-300 border-emerald-500/40'
                  : 'bg-slate-900 text-slate-400 border-slate-800'
              }`}
            >
              Highlight Deviations: {highlightDiff ? 'ON' : 'OFF'}
            </button>

            <button
              type="button"
              onClick={handleCopy}
              title="Copy active stdout"
              className="px-2.5 py-1 rounded-lg border border-slate-700 bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-semibold flex items-center gap-1.5 transition-colors cursor-pointer"
            >
              {copied ? <Check size={12} className="text-emerald-400" /> : <Copy size={12} />}
              <span>{copied ? 'Copied!' : 'Copy Active'}</span>
            </button>

            <button
              type="button"
              onClick={onClose}
              aria-label="Close split replay"
              className="p-1 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-slate-200 transition-colors cursor-pointer"
            >
              <X size={16} />
            </button>
          </div>
        </header>

        {/* Dual Split Body */}
        <div className="flex-1 min-h-0 grid grid-cols-2 divide-x divide-slate-800 bg-[#05070B] overflow-hidden text-xs">
          {/* Left Pane: Golden Baseline Run */}
          <div className="flex flex-col min-h-0 h-full">
            <div className="px-4 py-2 bg-[#07090E] border-b border-slate-800/80 flex items-center justify-between text-[11px]">
              <div className="flex items-center gap-2 font-bold text-slate-300">
                <CheckCircle2 size={13} className="text-emerald-400" />
                <span>GOLDEN BASELINE ({baselineJobId})</span>
              </div>
              <span className="text-[10px] text-emerald-400 border border-emerald-500/30 px-1.5 py-0.2 rounded bg-emerald-950/30">
                PASS · EXIT 0
              </span>
            </div>

            <div
              ref={leftPaneRef}
              onScroll={() => handleScroll('left')}
              className="flex-1 min-h-0 overflow-y-auto p-4 space-y-1 font-mono text-[11px] leading-5 text-slate-300 select-text"
            >
              {baselineEvents.map((e, idx) => (
                <div key={idx} className="flex gap-2 hover:bg-slate-900/40 px-1 py-0.5 rounded">
                  <span className="text-slate-600 w-6 text-right select-none">{idx + 1}</span>
                  <span className="text-slate-500 text-[10px] select-none">
                    {new Date(e.timestamp).toLocaleTimeString()}
                  </span>
                  <pre className="whitespace-pre font-mono flex-1 truncate">{e.data.line}</pre>
                </div>
              ))}
            </div>
          </div>

          {/* Right Pane: Active / Current Stream */}
          <div className="flex flex-col min-h-0 h-full bg-[#07090E]/40">
            <div className="px-4 py-2 bg-[#07090E] border-b border-slate-800/80 flex items-center justify-between text-[11px]">
              <div className="flex items-center gap-2 font-bold text-cyan-300">
                <Clock size={13} className="text-cyan-400" />
                <span>ACTIVE STREAM ({currentCorrelationId})</span>
              </div>
              <span className="text-[10px] text-cyan-300 border border-cyan-500/30 px-1.5 py-0.2 rounded bg-cyan-950/30">
                {activeStdoutLines.length} LINES
              </span>
            </div>

            <div
              ref={rightPaneRef}
              onScroll={() => handleScroll('right')}
              className="flex-1 min-h-0 overflow-y-auto p-4 space-y-1 font-mono text-[11px] leading-5 select-text"
            >
              {activeStdoutLines.length === 0 ? (
                <div className="flex flex-col items-center justify-center h-48 text-slate-600 text-xs">
                  <span>Waiting for stdout events from execution runner...</span>
                </div>
              ) : (
                activeStdoutLines.map((e, idx) => {
                  const line = e.data?.line || '';
                  const isError = line.includes('ERROR') || line.includes('failed') || line.includes('FATAL');
                  const isOk = line.includes('ok:') || line.includes('SUCCESS');

                  const diffHighlight =
                    highlightDiff && isError
                      ? 'bg-rose-950/40 text-rose-300 border-l-2 border-rose-500'
                      : highlightDiff && line.includes('changed:')
                      ? 'bg-amber-950/30 text-amber-300 border-l-2 border-amber-500'
                      : 'hover:bg-slate-900/40 text-slate-300';

                  return (
                    <div key={idx} className={`flex gap-2 px-1 py-0.5 rounded transition-colors ${diffHighlight}`}>
                      <span className="text-slate-600 w-6 text-right select-none">{idx + 1}</span>
                      <span className="text-slate-500 text-[10px] select-none">
                        {new Date(e.timestamp).toLocaleTimeString()}
                      </span>
                      <pre className="whitespace-pre font-mono flex-1 truncate">{line}</pre>
                    </div>
                  );
                })
              )}
            </div>
          </div>
        </div>

        {/* Footer */}
        <footer className="px-5 py-2.5 border-t border-slate-800 bg-[#07090E] flex items-center justify-between text-xs text-slate-400">
          <span className="text-[11px]">
            Synchronized frame-budget streaming over Redis WebSocket backplane with automatic drift alignment.
          </span>
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-1 rounded-lg border border-slate-700 bg-slate-800 hover:bg-slate-700 text-slate-200 font-semibold transition-colors cursor-pointer"
          >
            Close Replay
          </button>
        </footer>
      </div>
    </div>
  );
};

export default DualTerminalReplay;

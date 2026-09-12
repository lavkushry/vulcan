'use client';

import React, { useEffect, useState, useMemo } from 'react';
import {
  X,
  Code2,
  GitCompare,
  Copy,
  Check,
  FileCode,
  Layers,
  Sparkles,
  AlertTriangle,
  Activity
} from 'lucide-react';
import { api } from '@/lib/api';
import type { DeclarativeCodeDiff } from '@/lib/types';

interface MonacoDiffModalProps {
  correlationId: string;
  isOpen: boolean;
  onClose: () => void;
}

export const MonacoDiffModal: React.FC<MonacoDiffModalProps> = ({
  correlationId,
  isOpen,
  onClose
}) => {
  const [data, setData] = useState<DeclarativeCodeDiff | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<'split' | 'unified'>('split');
  const [copied, setCopied] = useState<boolean>(false);

  useEffect(() => {
    if (!isOpen || !correlationId) return;

    let mounted = true;
    setLoading(true);
    setError(null);

    api.getJobDiff(correlationId)
      .then((res) => {
        if (mounted) {
          setData(res);
          setLoading(false);
        }
      })
      .catch((err) => {
        if (mounted) {
          setError(err.message || 'Failed to generate declarative code diff');
          setLoading(false);
        }
      });

    return () => {
      mounted = false;
    };
  }, [isOpen, correlationId]);

  const handleCopy = () => {
    if (!data) return;
    const textToCopy = viewMode === 'unified' ? data.diff_unified : data.synthesized_code;
    navigator.clipboard.writeText(textToCopy);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const baseLines = useMemo(() => data?.base_code.split('\n') ?? [], [data]);
  const targetLines = useMemo(() => data?.synthesized_code.split('\n') ?? [], [data]);
  const unifiedLines = useMemo(() => data?.diff_unified.split('\n') ?? [], [data]);

  if (!isOpen) return null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="diff-modal-title"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-md p-4 animate-fadeIn"
      onClick={onClose}
    >
      <div
        className="w-full max-w-5xl h-[88vh] bg-[#0C101A] border border-slate-800 rounded-2xl flex flex-col font-mono shadow-2xl overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <header className="px-5 py-3.5 border-b border-slate-800 bg-[#07090E] flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2.5">
            <FileCode size={18} className="text-cyan-400" />
            <div>
              <h2 id="diff-modal-title" className="text-xs font-bold text-slate-100 uppercase tracking-wider flex items-center gap-2">
                <span>Declarative Code Diff Inspector</span>
                <span className="text-[10px] px-1.5 py-0.2 rounded border border-cyan-500/30 bg-cyan-950/40 text-cyan-300">
                  UI-23
                </span>
                {data && (
                  <span className="text-[10px] px-1.5 py-0.2 rounded border border-slate-700 bg-slate-800 text-slate-300 uppercase">
                    {data.engine}
                  </span>
                )}
              </h2>
              <p className="text-[10px] text-slate-500">
                {data ? `${data.file_path} · git ${data.git_head_sha.slice(0, 8)} vs ${data.synthesized_revision}` : 'Loading declarative plan...'}
              </p>
            </div>
          </div>

          {/* Controls: Mode Switcher & Copy */}
          <div className="flex items-center gap-2">
            <div className="flex items-center rounded-lg border border-slate-800 bg-[#07090E] p-0.5 text-xs">
              <button
                type="button"
                onClick={() => setViewMode('split')}
                className={`px-2.5 py-1 rounded text-[11px] font-semibold transition-colors ${
                  viewMode === 'split'
                    ? 'bg-cyan-950/60 text-cyan-300 border border-cyan-500/40'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                Side-by-Side
              </button>
              <button
                type="button"
                onClick={() => setViewMode('unified')}
                className={`px-2.5 py-1 rounded text-[11px] font-semibold transition-colors ${
                  viewMode === 'unified'
                    ? 'bg-cyan-950/60 text-cyan-300 border border-cyan-500/40'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                Unified Diff
              </button>
            </div>

            <button
              type="button"
              onClick={handleCopy}
              disabled={!data}
              title="Copy code to clipboard"
              className="px-2.5 py-1 rounded-lg border border-slate-700 bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-semibold flex items-center gap-1.5 transition-colors cursor-pointer"
            >
              {copied ? <Check size={12} className="text-emerald-400" /> : <Copy size={12} />}
              <span>{copied ? 'Copied!' : 'Copy'}</span>
            </button>

            <button
              type="button"
              onClick={onClose}
              aria-label="Close diff modal"
              className="p-1 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-slate-200 transition-colors cursor-pointer"
            >
              <X size={16} />
            </button>
          </div>
        </header>

        {/* Code Diff Body */}
        <div className="flex-1 min-h-0 bg-[#05070B] overflow-auto text-[11px] leading-5 select-text">
          {loading ? (
            <div className="flex flex-col items-center justify-center h-full gap-3 text-slate-500 text-xs font-mono">
              <Activity size={24} className="animate-spin text-cyan-400" />
              <span>Synthesizing declarative execution template &amp; parameter diff...</span>
            </div>
          ) : error ? (
            <div className="p-6 text-rose-400 flex items-center gap-2">
              <AlertTriangle size={18} />
              <span>{error}</span>
            </div>
          ) : data ? (
            viewMode === 'split' ? (
              /* Side-by-Side View */
              <div className="grid grid-cols-2 h-full divide-x divide-slate-800 font-mono">
                {/* Left: Base Code (HEAD) */}
                <div className="flex flex-col min-h-0 h-full overflow-hidden">
                  <div className="px-3 py-1.5 bg-[#07090E] border-b border-slate-800/80 text-[10px] text-slate-400 font-bold flex items-center justify-between">
                    <span>GIT HEAD BASELINE ({data.git_head_sha.slice(0, 8)})</span>
                    <span className="text-slate-600">ReadOnly Canonical</span>
                  </div>
                  <div className="flex-1 overflow-auto p-3 space-y-0.5">
                    {baseLines.map((line, idx) => (
                      <div key={idx} className="flex gap-3 hover:bg-slate-900/40 px-1 py-0.2 rounded">
                        <span className="text-slate-600 w-8 text-right select-none">{idx + 1}</span>
                        <pre className="text-slate-300 font-mono whitespace-pre">{line || ' '}</pre>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Right: Synthesized Target Code */}
                <div className="flex flex-col min-h-0 h-full overflow-hidden bg-emerald-950/5">
                  <div className="px-3 py-1.5 bg-[#07090E] border-b border-slate-800/80 text-[10px] text-emerald-400 font-bold flex items-center justify-between">
                    <span>SYNTHESIZED EXECUTION PLAN ({data.synthesized_revision})</span>
                    <span className="text-emerald-500/80">SOX-404 Parameter Bound</span>
                  </div>
                  <div className="flex-1 overflow-auto p-3 space-y-0.5">
                    {targetLines.map((line, idx) => {
                      const isAddition = line.includes('servicenow_chg') || line.includes('correlation_id') || line.includes('=') || line.includes(':');
                      return (
                        <div
                          key={idx}
                          className={`flex gap-3 px-1 py-0.2 rounded ${
                            isAddition ? 'bg-emerald-950/20 text-emerald-200' : 'hover:bg-slate-900/40 text-slate-300'
                          }`}
                        >
                          <span className="text-slate-600 w-8 text-right select-none">{idx + 1}</span>
                          <pre className="font-mono whitespace-pre">{line || ' '}</pre>
                        </div>
                      );
                    })}
                  </div>
                </div>
              </div>
            ) : (
              /* Unified Diff View */
              <div className="p-4 space-y-0.5 font-mono text-[11px]">
                {unifiedLines.map((line, idx) => {
                  const isAdd = line.startsWith('+') && !line.startsWith('+++');
                  const isDel = line.startsWith('-') && !line.startsWith('---');
                  const isHunk = line.startsWith('@@');

                  const lineStyle = isAdd
                    ? 'bg-emerald-950/30 text-emerald-300'
                    : isDel
                    ? 'bg-rose-950/30 text-rose-300'
                    : isHunk
                    ? 'text-cyan-400 font-bold bg-cyan-950/20'
                    : 'text-slate-400';

                  return (
                    <div key={idx} className={`px-2 py-0.5 rounded flex gap-3 ${lineStyle}`}>
                      <span className="w-8 text-right text-slate-600 select-none">{idx + 1}</span>
                      <pre className="whitespace-pre font-mono">{line || ' '}</pre>
                    </div>
                  );
                })}
              </div>
            )
          ) : null}
        </div>

        {/* Footer */}
        <footer className="px-5 py-2.5 border-t border-slate-800 bg-[#07090E] flex items-center justify-between text-[11px] text-slate-400">
          <div className="flex items-center gap-2">
            <Sparkles size={12} className="text-cyan-400" />
            <span>
              Declarative syntax verified with Pydantic grammar schemas prior to runner dispatch.
            </span>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-1 rounded-lg border border-slate-700 bg-slate-800 hover:bg-slate-700 text-slate-200 font-semibold transition-colors cursor-pointer"
          >
            Done
          </button>
        </footer>
      </div>
    </div>
  );
};

export default MonacoDiffModal;

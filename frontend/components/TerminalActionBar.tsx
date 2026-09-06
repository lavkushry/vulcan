'use client';

import React, { useState } from 'react';
import { Play, Pause, Copy, Check, Trash2, Search } from 'lucide-react';

export interface TerminalActionBarProps {
  onClear: () => void;
  onCopyStdout: () => void;
  isAutoscrollLocked: boolean;
  onToggleAutoscroll: () => void;
  bufferLines: number;
  maxBufferLines?: number;
  droppedLines?: number;
  searchQuery: string;
  onSearchChange: (query: string) => void;
}

export const TerminalActionBar: React.FC<TerminalActionBarProps> = ({
  onClear,
  onCopyStdout,
  isAutoscrollLocked,
  onToggleAutoscroll,
  bufferLines,
  maxBufferLines = 10000,
  droppedLines = 0,
  searchQuery,
  onSearchChange,
}) => {
  const [copied, setCopied] = useState<boolean>(false);

  const handleCopy = () => {
    onCopyStdout();
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  return (
    <div className="flex flex-wrap items-center justify-between gap-2 px-3 py-1.5 bg-[#07090E] border-b border-slate-800 font-mono text-xs select-none">
      {/* Status & Buffer counter */}
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-1.5">
          <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
          <span className="font-semibold text-slate-300 text-[11px]">LIVE STDOUT</span>
        </div>
        <span className="text-slate-600">|</span>
        <span className="text-[10px] text-slate-400">
          Buffer: <strong className="text-slate-300">{bufferLines}</strong> / {maxBufferLines} lines
          {droppedLines > 0 && (
            <span className="text-rose-400 ml-1">({droppedLines} dropped)</span>
          )}
        </span>
      </div>

      {/* Action Controls */}
      <div className="flex items-center gap-2">
        {/* Search */}
        <div className="relative flex items-center">
          <Search size={11} className="absolute left-2 text-slate-500 pointer-events-none" />
          <input
            type="text"
            placeholder="Regex search..."
            value={searchQuery}
            onChange={(e) => onSearchChange(e.target.value)}
            className="pl-6 pr-2 py-0.5 rounded bg-slate-900 border border-slate-800 text-[11px] text-slate-200 placeholder-slate-600 focus:outline-none focus:border-cyan-500 w-32 focus:w-44 transition-all"
          />
        </div>

        {/* Autoscroll Toggle */}
        <button
          type="button"
          onClick={onToggleAutoscroll}
          title={isAutoscrollLocked ? "Click to resume autoscroll" : "Click to freeze autoscroll"}
          className={`px-2 py-0.5 rounded text-[10px] font-semibold flex items-center gap-1 transition-colors ${
            isAutoscrollLocked
              ? 'bg-amber-500/20 text-amber-300 border border-amber-500/40'
              : 'bg-slate-800 text-slate-400 hover:text-slate-200 border border-slate-700'
          }`}
        >
          {isAutoscrollLocked ? (
            <>
              <Pause size={10} className="text-amber-400" />
              <span>Scroll Paused</span>
            </>
          ) : (
            <>
              <Play size={10} className="text-emerald-400" />
              <span>Auto-pin</span>
            </>
          )}
        </button>

        {/* Copy Raw */}
        <button
          type="button"
          onClick={handleCopy}
          title="Copy clean ANSI-stripped stdout to clipboard"
          className="px-2 py-0.5 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 text-[10px] flex items-center gap-1 transition-colors"
        >
          {copied ? (
            <>
              <Check size={10} className="text-emerald-400" />
              <span className="text-emerald-400 font-bold">Copied!</span>
            </>
          ) : (
            <>
              <Copy size={10} />
              <span>Copy Raw</span>
            </>
          )}
        </button>

        {/* Clear */}
        <button
          type="button"
          onClick={onClear}
          title="Clear screen buffer"
          className="px-2 py-0.5 rounded bg-slate-800 hover:bg-slate-700 text-slate-400 hover:text-slate-200 border border-slate-700 text-[10px] flex items-center gap-1 transition-colors"
        >
          <Trash2 size={10} />
          <span>Clear</span>
        </button>
      </div>
    </div>
  );
};

export default TerminalActionBar;

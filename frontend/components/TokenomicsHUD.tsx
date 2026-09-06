'use client';

import React from 'react';

export interface TokenomicsProps {
  maxTokens?: number; // default 2500
  promptTokens?: number; // e.g. 860
  completionTokens?: number; // e.g. 180
  latencyMs?: number; // e.g. 320
  ttftMs?: number; // e.g. 48
  decodeSpeedTokPerSec?: number; // e.g. 122
  intentConfidencePercent?: number; // e.g. 99.4
  cosineDistance?: number; // e.g. 0.082
  matchedCatalogItem?: string; // 'net-f5-cert-renew'
  prefixCacheTokens?: number; // 400
}

export const TokenomicsHUD: React.FC<TokenomicsProps> = ({
  maxTokens = 2500,
  promptTokens = 840,
  completionTokens = 180,
  latencyMs = 320,
  ttftMs = 48,
  decodeSpeedTokPerSec = 122,
  intentConfidencePercent = 99.4,
  cosineDistance = 0.082,
  matchedCatalogItem = 'net-f5-cert-renew',
  prefixCacheTokens = 400,
}) => {
  const totalTokens = promptTokens + completionTokens;
  const percentUsed = Math.min(100, (totalTokens / maxTokens) * 100);

  return (
    <div className="p-3 rounded-lg bg-[#0C101A] border border-slate-800 font-mono text-xs flex flex-col gap-2 shadow-inner">
      <div className="flex items-center justify-between text-slate-300">
        <div className="flex items-center gap-2">
          <span className="text-cyan-400">🧠</span>
          <span className="font-semibold text-slate-200">LLM OS Working Memory</span>
        </div>
        <div className="flex items-center gap-2 text-[11px] text-slate-400">
          <span>
            TTFT: <strong className="text-cyan-400">{ttftMs}ms</strong>
          </span>
          <span>•</span>
          <span>
            Decode: <strong className="text-emerald-400">{decodeSpeedTokPerSec} tok/s</strong>
          </span>
          <span>•</span>
          <span>
            Latency: <strong className="text-slate-200">{latencyMs}ms</strong>
          </span>
        </div>
      </div>

      {/* Segmented Memory Bar */}
      <div className="relative w-full h-2 rounded-full bg-slate-900 border border-slate-800 overflow-hidden">
        <div
          style={{ width: `${percentUsed}%` }}
          className="h-full bg-gradient-to-r from-cyan-500 via-blue-500 to-emerald-400 transition-all duration-300"
        />
      </div>

      <div className="flex items-center justify-between text-[10px] text-slate-400">
        <span>
          RAM Budget: <strong className="text-slate-200">{totalTokens}</strong> / {maxTokens} tokens ({percentUsed.toFixed(1)}% utilized)
        </span>
        <span>
          Prefix-Cache VRAM: <strong className="text-emerald-400">{prefixCacheTokens} tok (HIT)</strong>
        </span>
      </div>

      {/* Intent Calibration & Grammar Guard */}
      <div className="mt-1 pt-2 border-t border-slate-800/80 flex flex-wrap items-center justify-between gap-2 text-[11px]">
        <div className="flex items-center gap-1.5">
          <span className="text-slate-400">Intent Match:</span>
          <span className="text-emerald-400 font-bold">{intentConfidencePercent}%</span>
          <span className="text-slate-500">[{matchedCatalogItem}]</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-slate-400">
            HNSW Dist: <code className="text-cyan-400">{cosineDistance}</code>
          </span>
          <span className="px-1.5 py-0.5 rounded bg-emerald-950/40 text-emerald-300 border border-emerald-500/30 text-[10px]">
            ✓ Pydantic FSM Valid
          </span>
        </div>
      </div>
    </div>
  );
};

export default TokenomicsHUD;

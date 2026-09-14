'use client';

import React from 'react';

export interface TokenomicsProps {
  maxTokens?: number;
  promptTokens?: number;
  completionTokens?: number;
  latencyMs?: number;
  ttftMs?: number;
  decodeSpeedTokPerSec?: number;
  intentConfidencePercent?: number;
  cosineDistance?: number;
  matchedCatalogItem?: string;
  prefixCacheTokens?: number;
}

export const TokenomicsHUD: React.FC<TokenomicsProps> = ({
  maxTokens,
  promptTokens,
  completionTokens,
  latencyMs,
  ttftMs,
  decodeSpeedTokPerSec,
  intentConfidencePercent,
  cosineDistance,
  matchedCatalogItem,
  prefixCacheTokens,
}) => {
  const hasTokens = promptTokens !== undefined && completionTokens !== undefined;
  const totalTokens = hasTokens ? promptTokens + completionTokens : undefined;
  const percentUsed = (totalTokens !== undefined && maxTokens) ? Math.min(100, (totalTokens / maxTokens) * 100) : undefined;

  return (
    <div className="p-3 rounded-lg bg-[#0C101A] border border-slate-800 font-mono text-xs flex flex-col gap-2 shadow-inner">
      <div className="flex items-center justify-between text-slate-300">
        <div className="flex items-center gap-2">
          <span className="text-cyan-400">🧠</span>
          <span className="font-semibold text-slate-200">LLM Working Memory</span>
          <span className="text-[9px] px-1.5 py-0.2 rounded bg-slate-800 text-slate-400 border border-slate-700">Measured</span>
        </div>
        <div className="flex items-center gap-2 text-[11px] text-slate-400">
          <span>
            TTFT: <strong className={ttftMs ? "text-cyan-400" : "text-slate-500 font-normal"}>{ttftMs ? `${ttftMs}ms` : "Unavailable"}</strong>
          </span>
          <span>•</span>
          <span>
            Decode: <strong className={decodeSpeedTokPerSec ? "text-emerald-400" : "text-slate-500 font-normal"}>{decodeSpeedTokPerSec ? `${decodeSpeedTokPerSec} tok/s` : "Unavailable"}</strong>
          </span>
          <span>•</span>
          <span>
            Latency: <strong className={latencyMs ? "text-slate-200" : "text-slate-500 font-normal"}>{latencyMs ? `${latencyMs}ms` : "Unavailable"}</strong>
          </span>
        </div>
      </div>

      {/* Segmented Memory Bar */}
      <div className="relative w-full h-2 rounded-full bg-slate-900 border border-slate-800 overflow-hidden">
        {percentUsed !== undefined ? (
          <div
            style={{ width: `${percentUsed}%` }}
            className="h-full bg-gradient-to-r from-cyan-500 to-emerald-400 transition-all duration-300"
          />
        ) : (
          <div className="h-full w-full bg-slate-800/40" />
        )}
      </div>

      <div className="flex items-center justify-between text-[10px] text-slate-400">
        <span>
          RAM Budget: {totalTokens !== undefined && maxTokens ? (
            <><strong className="text-slate-200">{totalTokens}</strong> / {maxTokens} tokens ({percentUsed?.toFixed(1)}% utilized)</>
          ) : (
            <span className="text-slate-500">Unavailable</span>
          )}
        </span>
        <span>
          Prefix-Cache VRAM: {prefixCacheTokens !== undefined ? (
            <strong className="text-emerald-400">{prefixCacheTokens} tok</strong>
          ) : (
            <span className="text-slate-500">Unavailable</span>
          )}
        </span>
      </div>

      {/* Intent Calibration & Grammar Guard */}
      <div className="mt-1 pt-2 border-t border-slate-800/80 flex flex-wrap items-center justify-between gap-2 text-[11px]">
        <div className="flex items-center gap-1.5">
          <span className="text-slate-400">Intent Match:</span>
          {intentConfidencePercent !== undefined ? (
            <span className="text-emerald-400 font-bold">{intentConfidencePercent}%</span>
          ) : (
            <span className="text-slate-500">Unavailable</span>
          )}
          {matchedCatalogItem && <span className="text-slate-500">[{matchedCatalogItem}]</span>}
        </div>
        <div className="flex items-center gap-2">
          <span className="text-slate-400">
            HNSW Dist: {cosineDistance !== undefined ? (
              <code className="text-cyan-400">{cosineDistance}</code>
            ) : (
              <span className="text-slate-500">Unavailable</span>
            )}
          </span>
        </div>
      </div>
    </div>
  );
};

export default TokenomicsHUD;

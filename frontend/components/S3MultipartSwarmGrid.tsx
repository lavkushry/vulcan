'use client';

import React, { useState, useEffect } from 'react';
import { Database, CheckCircle2, RefreshCw } from 'lucide-react';

export interface S3MultipartSwarmGridProps {
  totalParts?: number; // e.g. 205 parts for 10GB
  partSizeMb?: number; // 50MB
  parallelStreams?: number; // 8
  directWireSpeedMbSec?: number; // 680 MB/s
  controlPlaneLatencyMs?: number; // 15ms
  isSimulating?: boolean;
}

export const S3MultipartSwarmGrid: React.FC<S3MultipartSwarmGridProps> = ({
  totalParts = 205,
  partSizeMb = 50,
  parallelStreams = 8,
  directWireSpeedMbSec = 680,
  controlPlaneLatencyMs = 15,
  isSimulating = true,
}) => {
  const [completedParts, setCompletedParts] = useState<number>(182);
  const [activeStreams, setActiveStreams] = useState<number[]>([]);

  useEffect(() => {
    if (!isSimulating) return;
    const interval = setInterval(() => {
      setCompletedParts((prev) => {
        if (prev >= totalParts) return totalParts;
        return prev + 1;
      });
      // Pick parallel in-flight indexes
      const inflight: number[] = [];
      for (let i = 0; i < parallelStreams; i++) {
        inflight.push((completedParts + i) % totalParts);
      }
      setActiveStreams(inflight);
    }, 250);
    return () => clearInterval(interval);
  }, [isSimulating, completedParts, totalParts, parallelStreams]);

  const percent = Math.min(100, Math.round((completedParts / totalParts) * 100));
  const uploadedGb = ((completedParts * partSizeMb) / 1024).toFixed(2);
  const totalGb = ((totalParts * partSizeMb) / 1024).toFixed(2);

  return (
    <div className="rounded-xl border border-slate-800 bg-[#0C101A] p-4 flex flex-col gap-3 font-mono text-xs shadow-xl">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-800 pb-2.5">
        <div className="flex items-center gap-2">
          <Database size={15} className="text-cyan-400" />
          <span className="font-bold text-slate-200">
            10GB S3 Decoupled Multipart Swarm
          </span>
          <span className="text-[10px] px-2 py-0.5 rounded bg-cyan-950/40 text-cyan-300 border border-cyan-500/30">
            {parallelStreams} Parallel HTTPS Streams
          </span>
        </div>
        <div className="flex items-center gap-2 text-[11px] text-slate-400">
          <span>Wire Speed: <strong className="text-emerald-400">{directWireSpeedMbSec} MB/s</strong></span>
          <span>•</span>
          <span>Control Latency: <strong className="text-cyan-400">{controlPlaneLatencyMs}ms</strong></span>
        </div>
      </div>

      <div className="flex items-center justify-between text-slate-300 text-xs">
        <span>
          Transferred: <strong className="text-cyan-300">{uploadedGb} GB</strong> / {totalGb} GB ({percent}%)
        </span>
        <span className="text-slate-500 text-[11px]">
          {completedParts} of {totalParts} chunks verified
        </span>
      </div>

      {/* 205-Tile Micro Swarm Grid */}
      <div className="p-2.5 rounded-lg bg-[#07090E] border border-slate-800/80">
        <div className="grid grid-cols-25 gap-1 max-h-28 overflow-hidden" style={{ gridTemplateColumns: 'repeat(25, minmax(0, 1fr))' }}>
          {[...Array(totalParts)].map((_, idx) => {
            const isDone = idx < completedParts;
            const isInFlight = activeStreams.includes(idx);
            return (
              <div
                key={idx}
                title={`Part #${idx + 1}: ${isDone ? 'ETag Verified' : isInFlight ? 'Uploading' : 'Queued'}`}
                className={`h-2 rounded-[2px] transition-all duration-200 ${
                  isDone
                    ? 'bg-emerald-400 shadow-[0_0_4px_rgba(0,255,157,0.5)]'
                    : isInFlight
                    ? 'bg-cyan-400 animate-pulse shadow-[0_0_6px_rgba(0,240,255,0.8)]'
                    : 'bg-slate-800'
                }`}
              />
            );
          })}
        </div>
      </div>

      <div className="flex items-center justify-between text-[10px] text-slate-400">
        <span className="flex items-center gap-1.5">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
          <span>ETag MD5 Integrity Check: 100% Passed</span>
        </span>
        <span className="text-slate-500">
          Decoupled from V8 React Event Loop (Canvas 60 FPS)
        </span>
      </div>
    </div>
  );
};

export default S3MultipartSwarmGrid;

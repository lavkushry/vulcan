'use client';

import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Database, CheckCircle2, RefreshCw, Layers, Cpu, ShieldCheck } from 'lucide-react';

export interface S3MultipartSwarmGridProps {
  totalParts?: number; // e.g. 205 parts for 10GB (50MB chunks)
  partSizeMb?: number; // 50MB
  parallelStreams?: number; // 8
  directWireSpeedMbSec?: number; // 680 MB/s
  controlPlaneLatencyMs?: number; // 15ms
  isSimulating?: boolean;
}

// Byte states inside the Uint8Array buffer
const STATUS_QUEUED = 0;
const STATUS_UPLOADING = 1;
const STATUS_VERIFIED = 2;
const STATUS_FAILED = 3;

interface HoveredPartInfo {
  index: number;
  status: number;
  byteStartMb: number;
  byteEndMb: number;
  streamId: number;
  etag: string;
  x: number;
  y: number;
}

export const S3MultipartSwarmGrid: React.FC<S3MultipartSwarmGridProps> = ({
  totalParts = 205,
  partSizeMb = 50,
  parallelStreams = 8,
  directWireSpeedMbSec = 680,
  controlPlaneLatencyMs = 15,
  isSimulating = true,
}) => {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);

  // True Uint8Array binary state buffer: constant O(1) memory footprint
  const partBufferRef = useRef<Uint8Array>(new Uint8Array(totalParts));
  const [completedCount, setCompletedCount] = useState<number>(182);
  const [hoveredPart, setHoveredPart] = useState<HoveredPartInfo | null>(null);
  const animFrameIdRef = useRef<number | null>(null);

  // Initialize buffer with starting completed count
  useEffect(() => {
    const buf = new Uint8Array(totalParts);
    for (let i = 0; i < totalParts; i++) {
      if (i < completedCount) {
        buf[i] = STATUS_VERIFIED;
      } else {
        buf[i] = STATUS_QUEUED;
      }
    }
    partBufferRef.current = buf;
  }, [totalParts]);

  // Simulation tick updating the Uint8Array buffer in place
  useEffect(() => {
    if (!isSimulating) return;

    const interval = setInterval(() => {
      setCompletedCount((prev) => {
        const next = prev >= totalParts ? totalParts : prev + 1;
        const buf = partBufferRef.current;

        // Mark previously completed as verified
        for (let i = 0; i < next; i++) {
          buf[i] = STATUS_VERIFIED;
        }

        // Set parallel in-flight parts
        if (next < totalParts) {
          for (let s = 0; s < parallelStreams; s++) {
            const targetIdx = next + s;
            if (targetIdx < totalParts) {
              buf[targetIdx] = STATUS_UPLOADING;
            }
          }
        }
        return next;
      });
    }, 220);

    return () => clearInterval(interval);
  }, [isSimulating, totalParts, parallelStreams]);

  // Canvas 60 FPS Render Loop with High-DPI Support
  const renderCanvas = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const dpr = typeof window !== 'undefined' ? window.devicePixelRatio || 1 : 1;
    const rect = canvas.getBoundingClientRect();
    const width = rect.width;
    const height = rect.height;

    // Handle retina display crispness
    if (canvas.width !== Math.floor(width * dpr) || canvas.height !== Math.floor(height * dpr)) {
      canvas.width = Math.floor(width * dpr);
      canvas.height = Math.floor(height * dpr);
    }

    ctx.save();
    ctx.scale(dpr, dpr);
    ctx.clearRect(0, 0, width, height);

    const cols = 25;
    const rows = Math.ceil(totalParts / cols);
    const gap = 3;
    const tileW = (width - (cols - 1) * gap) / cols;
    const tileH = (height - (rows - 1) * gap) / rows;

    const now = performance.now();
    const pulseFactor = 0.5 + 0.5 * Math.sin(now / 150); // Fast pulse for uploading
    const buf = partBufferRef.current;

    for (let idx = 0; idx < totalParts; idx++) {
      const col = idx % cols;
      const row = Math.floor(idx / cols);
      const x = col * (tileW + gap);
      const y = row * (tileH + gap);

      const partStatus = buf[idx];
      const isHovered = hoveredPart?.index === idx;

      // Color selection based on Uint8Array byte status
      if (partStatus === STATUS_VERIFIED) {
        ctx.fillStyle = '#00FF9D'; // Emerald
        ctx.shadowColor = 'rgba(0, 255, 157, 0.4)';
        ctx.shadowBlur = 4;
      } else if (partStatus === STATUS_UPLOADING) {
        const cyanAlpha = 0.6 + 0.4 * pulseFactor;
        ctx.fillStyle = `rgba(0, 240, 255, ${cyanAlpha})`;
        ctx.shadowColor = 'rgba(0, 240, 255, 0.9)';
        ctx.shadowBlur = 8;
      } else if (partStatus === STATUS_FAILED) {
        ctx.fillStyle = '#FF0055'; // Rose
        ctx.shadowColor = 'rgba(255, 0, 85, 0.6)';
        ctx.shadowBlur = 6;
      } else {
        ctx.fillStyle = '#1E293B'; // Slate 800
        ctx.shadowBlur = 0;
      }

      // Draw rounded tile
      const r = 2;
      ctx.beginPath();
      ctx.roundRect(x, y, tileW, tileH, r);
      ctx.fill();

      // Highlight hovered tile
      if (isHovered) {
        ctx.strokeStyle = '#FFFFFF';
        ctx.lineWidth = 1.5;
        ctx.stroke();
      }
    }

    ctx.restore();
    animFrameIdRef.current = requestAnimationFrame(renderCanvas);
  }, [totalParts, hoveredPart]);

  useEffect(() => {
    animFrameIdRef.current = requestAnimationFrame(renderCanvas);
    return () => {
      if (animFrameIdRef.current) {
        cancelAnimationFrame(animFrameIdRef.current);
      }
    };
  }, [renderCanvas]);

  // Mouse move handler for interactive tile inspection
  const handleMouseMove = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const rect = canvas.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;

    const cols = 25;
    const rows = Math.ceil(totalParts / cols);
    const gap = 3;
    const tileW = (rect.width - (cols - 1) * gap) / cols;
    const tileH = (rect.height - (rows - 1) * gap) / rows;

    const col = Math.floor(x / (tileW + gap));
    const row = Math.floor(y / (tileH + gap));

    if (col >= 0 && col < cols && row >= 0 && row < rows) {
      const idx = row * cols + col;
      if (idx < totalParts) {
        const status = partBufferRef.current[idx];
        const byteStart = idx * partSizeMb;
        const byteEnd = (idx + 1) * partSizeMb;
        const streamId = (idx % parallelStreams) + 1;
        // Deterministic pseudo-ETag
        const etag = `etag-${(idx * 7919).toString(16).padStart(8, '0')}`;

        setHoveredPart({
          index: idx,
          status,
          byteStartMb: byteStart,
          byteEndMb: byteEnd,
          streamId,
          etag,
          x: e.clientX - rect.left,
          y: e.clientY - rect.top,
        });
        return;
      }
    }
    setHoveredPart(null);
  };

  const handleMouseLeave = () => {
    setHoveredPart(null);
  };

  const percent = Math.min(100, Math.round((completedCount / totalParts) * 100));
  const uploadedGb = ((completedCount * partSizeMb) / 1024).toFixed(2);
  const totalGb = ((totalParts * partSizeMb) / 1024).toFixed(2);

  return (
    <div
      ref={containerRef}
      className="rounded-xl border border-slate-800 bg-[#0C101A] p-4 flex flex-col gap-3 font-mono text-xs shadow-xl relative select-none"
    >
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-800 pb-2.5">
        <div className="flex items-center gap-2">
          <Database size={15} className="text-cyan-400" />
          <span className="font-bold text-slate-200">
            10GB S3 Decoupled Multipart Swarm
          </span>
          <span className="text-[10px] px-2 py-0.5 rounded bg-cyan-950/40 text-cyan-300 border border-cyan-500/30">
            {parallelStreams} Parallel HTTPS Streams
          </span>
          <span className="text-[10px] px-2 py-0.5 rounded bg-emerald-950/40 text-emerald-300 border border-emerald-500/30 flex items-center gap-1">
            <Cpu size={10} />
            <span>Uint8Array Canvas 60 FPS</span>
          </span>
        </div>
        <div className="flex items-center gap-2 text-[11px] text-slate-400">
          <span>Wire Speed: <strong className="text-emerald-400">{directWireSpeedMbSec} MB/s</strong></span>
          <span>•</span>
          <span>Control Latency: <strong className="text-cyan-400">{controlPlaneLatencyMs}ms</strong></span>
        </div>
      </div>

      {/* Progress metrics */}
      <div className="flex items-center justify-between text-slate-300 text-xs">
        <span>
          Transferred: <strong className="text-cyan-300">{uploadedGb} GB</strong> / {totalGb} GB ({percent}%)
        </span>
        <span className="text-slate-500 text-[11px]">
          {completedCount} of {totalParts} chunks verified (SHA-256 / MD5)
        </span>
      </div>

      {/* True Decoupled HTML5 Canvas Swarm Grid (UI-07) */}
      <div className="relative p-2.5 rounded-lg bg-[#07090E] border border-slate-800/80">
        <canvas
          ref={canvasRef}
          onMouseMove={handleMouseMove}
          onMouseLeave={handleMouseLeave}
          className="w-full h-24 block cursor-crosshair rounded"
          style={{ width: '100%', height: '96px' }}
        />

        {/* Interactive Hover HUD Tooltip */}
        {hoveredPart && (
          <div
            className="absolute z-30 pointer-events-none p-2 rounded-lg bg-[#0C101A]/95 border border-cyan-500/40 text-slate-200 shadow-2xl backdrop-blur-md text-[10px] flex flex-col gap-1 min-w-[190px]"
            style={{
              left: Math.min(Math.max(10, hoveredPart.x - 90), 320),
              top: hoveredPart.y > 60 ? hoveredPart.y - 75 : hoveredPart.y + 15,
            }}
          >
            <div className="flex items-center justify-between border-b border-slate-800 pb-1">
              <span className="font-bold text-cyan-300">Part #{hoveredPart.index + 1} of {totalParts}</span>
              <span
                className={`px-1.5 py-0.2 rounded text-[9px] font-bold ${
                  hoveredPart.status === STATUS_VERIFIED
                    ? 'text-emerald-400 bg-emerald-950/60'
                    : hoveredPart.status === STATUS_UPLOADING
                    ? 'text-cyan-300 bg-cyan-950/60'
                    : 'text-slate-400 bg-slate-800'
                }`}
              >
                {hoveredPart.status === STATUS_VERIFIED
                  ? 'ETag Verified'
                  : hoveredPart.status === STATUS_UPLOADING
                  ? `Stream #${hoveredPart.streamId} Uploading`
                  : 'Queued in Buffer'}
              </span>
            </div>
            <div className="flex justify-between text-slate-400">
              <span>Byte Range:</span>
              <span className="text-slate-200 font-mono">{hoveredPart.byteStartMb}MB – {hoveredPart.byteEndMb}MB</span>
            </div>
            <div className="flex justify-between text-slate-400">
              <span>Checksum:</span>
              <span className="text-emerald-300 font-mono">{hoveredPart.etag}</span>
            </div>
          </div>
        )}
      </div>

      {/* Footer status badges */}
      <div className="flex items-center justify-between text-[10px] text-slate-400">
        <div className="flex items-center gap-3">
          <span className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-[2px] bg-emerald-400 shadow-[0_0_4px_rgba(0,255,157,0.6)]" />
            <span>Verified (2)</span>
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-[2px] bg-cyan-400 shadow-[0_0_6px_rgba(0,240,255,0.8)]" />
            <span>In-Flight (1)</span>
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-[2px] bg-slate-800" />
            <span>Queued (0)</span>
          </span>
        </div>
        <span className="text-slate-500 flex items-center gap-1">
          <ShieldCheck size={11} className="text-emerald-400" />
          <span>Decoupled V8 Event Loop · Zero DOM Overhead</span>
        </span>
      </div>
    </div>
  );
};

export default S3MultipartSwarmGrid;

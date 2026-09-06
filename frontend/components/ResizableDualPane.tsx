'use client';

import React, { useState, useEffect, useRef } from 'react';

interface ResizableDualPaneProps {
  leftPane: React.ReactNode;
  rightPane: React.ReactNode;
  storageKey?: string;
  defaultRatio?: number;
  minRatio?: number;
  maxRatio?: number;
  className?: string;
}

export const ResizableDualPane: React.FC<ResizableDualPaneProps> = ({
  leftPane,
  rightPane,
  storageKey = 'vulcan_chat_split_ratio',
  defaultRatio = 0.50,
  minRatio = 0.25,
  maxRatio = 0.75,
  className = '',
}) => {
  const [splitRatio, setSplitRatio] = useState<number>(defaultRatio);
  const [isDragging, setIsDragging] = useState<boolean>(false);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    try {
      const saved = localStorage.getItem(storageKey);
      if (saved) {
        const parsed = parseFloat(saved);
        if (!isNaN(parsed) && parsed >= minRatio && parsed <= maxRatio) {
          setSplitRatio(parsed);
        }
      }
    } catch {
      // Graceful fallback for SSR / restricted iframe
    }
  }, [storageKey, minRatio, maxRatio]);

  const handlePointerDown = (e: React.PointerEvent<HTMLDivElement>) => {
    e.currentTarget.setPointerCapture(e.pointerId);
    setIsDragging(true);
  };

  const handlePointerMove = (e: React.PointerEvent<HTMLDivElement>) => {
    if (!isDragging || !containerRef.current) return;
    const rect = containerRef.current.getBoundingClientRect();
    if (rect.width <= 0) return;
    const rawRatio = (e.clientX - rect.left) / rect.width;
    const clamped = Math.min(Math.max(rawRatio, minRatio), maxRatio);
    setSplitRatio(clamped);
  };

  const handlePointerUp = (e: React.PointerEvent<HTMLDivElement>) => {
    if (!isDragging) return;
    e.currentTarget.releasePointerCapture(e.pointerId);
    setIsDragging(false);
    try {
      localStorage.setItem(storageKey, splitRatio.toFixed(3));
    } catch {
      // Ignore
    }
  };

  const handleDoubleClick = () => {
    setSplitRatio(defaultRatio);
    try {
      localStorage.setItem(storageKey, defaultRatio.toFixed(3));
    } catch {
      // Ignore
    }
  };

  return (
    <div
      ref={containerRef}
      className={`relative flex w-full h-full overflow-hidden select-none bg-[#07090E] ${className}`}
    >
      {/* Left Pane */}
      <div
        style={{ width: `${(splitRatio * 100).toFixed(2)}%` }}
        className="h-full overflow-hidden flex flex-col min-w-0"
      >
        {leftPane}
      </div>

      {/* Draggable Divider */}
      <div
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
        onPointerUp={handlePointerUp}
        onDoubleClick={handleDoubleClick}
        role="separator"
        aria-valuenow={Math.round(splitRatio * 100)}
        aria-valuemin={Math.round(minRatio * 100)}
        aria-valuemax={Math.round(maxRatio * 100)}
        tabIndex={0}
        className={`group relative z-30 flex items-center justify-center w-2 cursor-col-resize transition-colors ${
          isDragging
            ? 'bg-cyan-500 shadow-[0_0_12px_rgba(0,240,255,0.8)]'
            : 'bg-[#121826] hover:bg-cyan-500/50'
        }`}
        title="Drag to resize panes (Double click to reset 50/50)"
      >
        <div className="w-0.5 h-8 rounded-full bg-slate-500 group-hover:bg-cyan-300 transition-colors" />
      </div>

      {/* Right Pane */}
      <div
        style={{ width: `${((1 - splitRatio) * 100).toFixed(2)}%` }}
        className="h-full overflow-hidden flex flex-col min-w-0"
      >
        {rightPane}
      </div>
    </div>
  );
};

export default ResizableDualPane;

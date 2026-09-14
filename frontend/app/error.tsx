'use client';

import React, { useEffect } from 'react';
import { AlertOctagon, RefreshCw, Home } from 'lucide-react';
import Link from 'next/link';

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error('Unhandled Application Error:', error);
  }, [error]);

  return (
    <div className="min-h-screen bg-canvas-void text-slate-200 flex items-center justify-center p-6 font-mono">
      <div className="max-w-md w-full bg-slate-900/80 border border-rose-500/40 rounded-xl p-6 shadow-2xl backdrop-blur-md space-y-4">
        <div className="flex items-center gap-3 text-rose-400">
          <div className="p-2 rounded-lg bg-rose-500/10 border border-rose-500/30">
            <AlertOctagon size={24} />
          </div>
          <div>
            <h1 className="text-sm font-bold tracking-wider uppercase text-white">System Exception Caught</h1>
            <p className="text-[11px] text-slate-400">Project Vulcan Obsidian Glass Safety Boundary</p>
          </div>
        </div>

        <div className="bg-slate-950/80 rounded p-3 border border-glass-border text-xs text-rose-300 break-words font-mono">
          {error?.message || 'An unexpected client-side exception occurred.'}
        </div>

        <div className="flex items-center justify-end gap-2 pt-2">
          <Link
            href="/"
            className="px-3 py-1.5 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs flex items-center gap-1.5"
          >
            <Home size={13} /> Dashboard
          </Link>
          <button
            onClick={() => reset()}
            className="px-3 py-1.5 rounded bg-rose-600 hover:bg-rose-500 text-white font-semibold text-xs flex items-center gap-1.5"
          >
            <RefreshCw size={13} /> Retry Component
          </button>
        </div>
      </div>
    </div>
  );
}

'use client';

import React from 'react';
import { AlertTriangle, ShieldCheck, Zap, RotateCcw, X, Cpu } from 'lucide-react';

interface DiagnosticData {
  fault_summary: string;
  root_cause: string;
  blast_radius: string;
  recommended_action: string;
  windowed_log: string;
  diagnosis_latency_ms: number;
}

interface DiagnosticDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  diagnostic: DiagnosticData | null;
  onTriggerRollback?: () => void;
}

export default function DiagnosticDrawer({
  isOpen,
  onClose,
  diagnostic,
  onTriggerRollback
}: DiagnosticDrawerProps) {
  if (!isOpen || !diagnostic) return null;

  return (
    <div className="fixed inset-y-0 right-0 z-50 w-full max-w-xl bg-canvas-void/95 backdrop-blur-xl border-l border-rose-500/30 shadow-2xl p-6 flex flex-col space-y-5 overflow-y-auto animate-in slide-in-from-right duration-300">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-rose-500/20 pb-4">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-rose-500/20 border border-rose-500/40 flex items-center justify-center text-rose-400 shadow-glow-crimson">
            <AlertTriangle className="w-5 h-5" />
          </div>
          <div>
            <h3 className="text-sm font-bold text-white tracking-wide flex items-center gap-2">
              AI SRE ROOT-CAUSE DIAGNOSIS
              <span className="text-[10px] px-2 py-0.5 rounded bg-rose-500/20 text-rose-300 font-mono">
                {diagnostic.diagnosis_latency_ms.toFixed(0)}MS LATENCY
              </span>
            </h3>
            <p className="text-xs text-slate-400 font-mono">50-Line Windowing & Failure Analysis</p>
          </div>
        </div>

        <button
          onClick={onClose}
          className="text-slate-400 hover:text-white p-1 rounded transition-colors"
        >
          <X className="w-5 h-5" />
        </button>
      </div>

      {/* Fault Summary */}
      <div className="bg-rose-950/20 border border-rose-500/30 rounded-lg p-4 space-y-2">
        <div className="text-[10px] font-mono text-rose-400 uppercase font-bold tracking-wider">
          Incident Classification
        </div>
        <div className="text-sm font-bold text-white">{diagnostic.fault_summary}</div>
      </div>

      {/* Root Cause & Blast Radius */}
      <div className="space-y-3 font-mono text-xs">
        <div className="bg-glass-raised p-4 rounded-lg border border-glass-border space-y-1.5">
          <div className="text-[10px] text-cyan-400 uppercase font-bold flex items-center gap-1.5">
            <Cpu className="w-3.5 h-3.5" /> Technical Root Cause
          </div>
          <p className="text-slate-300 leading-relaxed">{diagnostic.root_cause}</p>
        </div>

        <div className="bg-glass-raised p-4 rounded-lg border border-glass-border space-y-1.5">
          <div className="text-[10px] text-amber-400 uppercase font-bold flex items-center gap-1.5">
            <Zap className="w-3.5 h-3.5" /> Potential Blast Radius
          </div>
          <p className="text-slate-300 leading-relaxed">{diagnostic.blast_radius}</p>
        </div>

        <div className="bg-glass-raised p-4 rounded-lg border border-glass-border space-y-1.5">
          <div className="text-[10px] text-emerald-400 uppercase font-bold flex items-center gap-1.5">
            <ShieldCheck className="w-3.5 h-3.5" /> Prescribed Remediation
          </div>
          <p className="text-slate-300 leading-relaxed">{diagnostic.recommended_action}</p>
        </div>
      </div>

      {/* 50-Line Windowed Log Slices */}
      <div className="space-y-1.5 flex-1 font-mono text-xs">
        <div className="text-[10px] text-slate-400 uppercase font-bold">
          Software 1.0 Bounded Fault Window (50 Lines)
        </div>
        <pre className="bg-black/90 text-rose-300/90 p-3 rounded-lg border border-rose-500/20 text-[11px] overflow-x-auto max-h-[180px]">
          {diagnostic.windowed_log}
        </pre>
      </div>

      {/* Action Footer */}
      <div className="pt-2 flex items-center justify-end gap-3 border-t border-glass-border">
        <button
          onClick={onClose}
          className="px-4 py-2 rounded bg-glass-raised border border-glass-border text-slate-300 text-xs font-mono font-bold hover:bg-glass-overlay transition-colors"
        >
          DISMISS DRAWER
        </button>

        <button
          onClick={() => {
            if (onTriggerRollback) onTriggerRollback();
            onClose();
          }}
          className="px-5 py-2 rounded bg-rose-600 hover:bg-rose-500 text-white text-xs font-mono font-bold shadow-glow-crimson transition-all flex items-center gap-1.5"
        >
          <RotateCcw className="w-4 h-4" />
          DISPATCH AUTOMATED ROLLBACK
        </button>
      </div>
    </div>
  );
}

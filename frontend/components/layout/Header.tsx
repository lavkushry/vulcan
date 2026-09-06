'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { Search, Users, Activity, Shield, Database, Command } from 'lucide-react';
import { DEMO_USERS } from '@/lib/api';

interface HeaderProps {
  currentUser: string;
  onUserChange: (userId: string) => void;
  onOpenCommandPalette: () => void;
}

interface HealthData {
  status: string;
  catalog_size: number;
  active_jobs_count: number;
  audit_chain_valid: boolean;
  audit_tip_hash: string | null;
}

export function Header({ currentUser, onUserChange, onOpenCommandPalette }: HeaderProps) {
  const [health, setHealth] = useState<HealthData | null>(null);

  useEffect(() => {
    const BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';
    const fetchHealth = async () => {
      try {
        const res = await fetch(`${BASE}/api/v1/health`);
        if (res.ok) setHealth(await res.json());
      } catch { /* backend may be down */ }
    };
    fetchHealth();
    const t = setInterval(fetchHealth, 10000);
    return () => clearInterval(t);
  }, []);

  // Global Cmd+K listener
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        onOpenCommandPalette();
      }
    };
    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, [onOpenCommandPalette]);

  const currentUserObj = DEMO_USERS.find((u) => u.id === currentUser) ?? DEMO_USERS[0];

  return (
    <header className="sticky top-0 z-50 border-b border-glass-border bg-canvas-void/90 backdrop-blur-xl px-4 h-12 flex items-center justify-between">
      {/* Left: Brand */}
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-2">
          <div className="w-2.5 h-2.5 rounded-full bg-cyan-400 shadow-glow-cyan animate-pulse" />
          <span className="font-bold text-sm tracking-wider text-white">VULCAN</span>
        </div>
        <span className="text-[10px] px-1.5 py-0.5 rounded border border-cyan-500/20 bg-cyan-950/30 text-cyan-400/80 font-mono hidden sm:inline">
          v1.0
        </span>
      </div>

      {/* Center: Cmd+K trigger */}
      <button
        onClick={onOpenCommandPalette}
        className="hidden md:flex items-center gap-2 px-3 py-1.5 rounded-lg border border-glass-border bg-glass-surface/50 text-slate-500 hover:text-slate-300 hover:border-slate-600 transition-colors text-xs"
      >
        <Search size={13} />
        <span>Search actions or type a command…</span>
        <kbd className="ml-2 px-1.5 py-0.5 rounded border border-slate-700 bg-slate-800/50 text-[10px] font-mono text-slate-400">
          ⌘K
        </kbd>
      </button>

      {/* Right: Telemetry + Persona */}
      <div className="flex items-center gap-4">
        {/* Telemetry indicators */}
        <div className="hidden lg:flex items-center gap-4 text-[10px] font-mono">
          {health && (
            <>
              <div className="flex items-center gap-1.5">
                <Database size={11} className="text-slate-500" />
                <span className="text-slate-500">CATALOG</span>
                <span className="text-cyan-400">{health.catalog_size}</span>
              </div>
              <div className="flex items-center gap-1.5">
                <Activity size={11} className="text-slate-500" />
                <span className="text-slate-500">ACTIVE</span>
                <span className="text-emerald-400">{health.active_jobs_count}</span>
              </div>
              <div className="flex items-center gap-1.5">
                <Shield size={11} className="text-slate-500" />
                <span className="text-slate-500">MERKLE</span>
                <span className={health.audit_chain_valid ? 'text-emerald-400' : 'text-rose-400'}>
                  {health.audit_chain_valid ? 'VALID' : 'BROKEN'}
                </span>
              </div>
            </>
          )}
        </div>

        {/* Persona switcher */}
        <div className="flex items-center gap-2 border-l border-glass-border pl-4">
          <Users size={13} className="text-slate-500" />
          <select
            value={currentUser}
            onChange={(e) => onUserChange(e.target.value)}
            className="bg-transparent text-xs text-slate-300 border-none outline-none cursor-pointer font-mono"
          >
            {DEMO_USERS.map((u) => (
              <option key={u.id} value={u.id} className="bg-canvas-void text-slate-200">
                {u.label}
              </option>
            ))}
          </select>
        </div>
      </div>
    </header>
  );
}

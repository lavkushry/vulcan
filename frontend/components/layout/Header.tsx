'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { Search, Users, Activity, Shield, Database, Command, Bell, CheckCircle2, Globe2, Lock } from 'lucide-react';
import { DEMO_USERS, api } from '@/lib/api';
import { useRouter } from 'next/navigation';
import { getApiBaseUrl } from '@/lib/env';
import { useVulcan } from '@/lib/context';
import ClusterMapModal from '../ClusterMapModal';

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
  const router = useRouter();
  const { authStatus, authenticatedUser, authenticatedRole, authenticatedRoleBadge, logout, openSignInModal } = useVulcan();
  const [health, setHealth] = useState<HealthData | null>(null);
  const [pendingCount, setPendingCount] = useState(0);
  const [isClusterMapOpen, setIsClusterMapOpen] = useState(false);

  useEffect(() => {
    const BASE = getApiBaseUrl();
    const fetchHealth = async () => {
      try {
        const res = await fetch(`${BASE}/api/v1/health`);
        if (res.ok) {
          const h = await res.json();
          setHealth(h);
        }
      } catch { /* backend may be starting */ }
    };
    const fetchJobs = async () => {
      try {
        const jobs = await api.listJobs();
        if (Array.isArray(jobs)) {
          const pending = jobs.filter(j => j.status === 'PENDING_APPROVAL').length;
          setPendingCount(pending);
        }
      } catch { /* ignore */ }
    };
    fetchHealth();
    fetchJobs();
    const tHealth = setInterval(fetchHealth, 5000);
    const tJobs = setInterval(fetchJobs, 5000);
    return () => {
      clearInterval(tHealth);
      clearInterval(tJobs);
    };
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
        <div className="hidden lg:flex items-center gap-3 text-[10px] font-mono">
          <div className="flex items-center gap-1.5">
            <Database size={11} className="text-slate-500" />
            <span className="text-slate-500">CATALOG</span>
            <span className={health?.catalog_size !== undefined ? "text-cyan-400" : "text-slate-500"}>
              {health?.catalog_size !== undefined ? health.catalog_size : "—"}
            </span>
          </div>
          <div className="flex items-center gap-1.5">
            <Activity size={11} className="text-slate-500" />
            <span className="text-slate-500">ACTIVE</span>
            <span className={health?.active_jobs_count !== undefined ? "text-emerald-400" : "text-slate-500"}>
              {health?.active_jobs_count !== undefined ? health.active_jobs_count : "0"}
            </span>
          </div>
          <div className="flex items-center gap-1.5">
            <Shield size={11} className="text-slate-500" />
            <span className="text-slate-500">MERKLE</span>
            <span className={health ? (health.audit_chain_valid ? 'text-emerald-400' : 'text-rose-400') : 'text-slate-500'}>
              {health ? (health.audit_chain_valid ? 'VALID' : 'BROKEN') : 'UNCHECKED'}
            </span>
          </div>
          <button
            type="button"
            onClick={() => setIsClusterMapOpen(true)}
            title="Inspect multi-datacenter cluster topology & Redlock consensus (UI-25)"
            className="flex items-center gap-1.5 text-slate-400 hover:text-cyan-300 transition-colors cursor-pointer"
            data-testid="header-cluster-radar-btn"
          >
            <Globe2 size={11} className="text-cyan-400" />
            <span className="text-slate-500">CLUSTERS</span>
          </button>
        </div>

        {/* Pending Approvals Notification Badge */}
        {pendingCount > 0 && (
          <button
            onClick={() => router.push('/history')}
            className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-amber-500/15 border border-amber-500/40 text-amber-300 font-mono text-[11px] hover:bg-amber-500/25 transition-all animate-pulse"
            title="Tasks awaiting Maker-Checker Lead Approval"
            aria-label={`${pendingCount} Pending Approvals awaiting Maker-Checker Lead Approval`}
          >
            <Bell size={12} className="text-amber-400" />
            <span>{pendingCount} Pending Approval{pendingCount > 1 ? 's' : ''}</span>
          </button>
        )}

        {/* Authenticated Identity or Sign In */}
        {authStatus === 'authenticated' ? (
          <div className="flex items-center gap-2 border-l border-glass-border pl-3">
            <span className={`text-[10px] font-mono px-2 py-0.5 rounded border hidden sm:inline ${
              authenticatedRole === 'APPROVING_LEAD'
                ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-300'
                : authenticatedRole === 'SECURITY_ADMIN'
                ? 'border-purple-500/30 bg-purple-500/10 text-purple-300'
                : authenticatedRole === 'PLATFORM_ADMIN'
                ? 'border-amber-500/30 bg-amber-500/10 text-amber-300'
                : authenticatedRole === 'AUDITOR'
                ? 'border-blue-500/30 bg-blue-500/10 text-blue-300'
                : 'border-cyan-500/30 bg-cyan-500/10 text-cyan-300'
            }`}>
              {authenticatedRoleBadge ?? authenticatedRole ?? 'OPERATOR'}
            </span>
            <span className="text-xs font-mono text-slate-200 font-semibold">
              {authenticatedUser}
            </span>
            <button
              onClick={logout}
              title="Sign out of current session"
              className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-slate-800 hover:bg-slate-700 text-slate-400 hover:text-rose-300 transition-colors ml-1 cursor-pointer"
            >
              Sign out
            </button>
          </div>
        ) : (
          <div className="flex items-center gap-2 border-l border-glass-border pl-3">
            <span className="text-[10px] font-mono px-2 py-0.5 rounded border border-slate-700 bg-slate-900 text-slate-400 hidden sm:inline">
              UNAUTHENTICATED
            </span>
            <button
              onClick={openSignInModal}
              data-testid="header-sign-in-btn"
              className="flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-cyan-500/20 hover:bg-cyan-500/30 border border-cyan-500/40 text-cyan-300 font-mono text-xs font-semibold transition-all cursor-pointer shadow-glow-cyan"
            >
              <Lock size={12} className="text-cyan-400" />
              <span>Sign In</span>
            </button>
          </div>
        )}
      </div>

      {/* Multi-Cluster Topology Radar Modal (UI-25) */}
      <ClusterMapModal
        isOpen={isClusterMapOpen}
        onClose={() => setIsClusterMapOpen(false)}
      />
    </header>
  );
}

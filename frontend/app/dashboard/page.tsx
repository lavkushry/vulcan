'use client';

import React, { useState, useEffect, useMemo } from 'react';
import {
  Database, Activity, Clock, AlertTriangle, CheckCircle2, XCircle,
  Shield, TrendingUp, ArrowRight
} from 'lucide-react';
import { AppShell } from '@/components/layout/AppShell';
import { api } from '@/lib/api';
import type { Job } from '@/lib/types';
import { useRouter } from 'next/navigation';

interface HealthData {
  status: string;
  catalog_size: number;
  active_jobs_count: number;
  audit_chain_valid: boolean;
  audit_tip_hash: string | null;
}

function DashboardContent() {
  const router = useRouter();
  const [health, setHealth] = useState<HealthData | null>(null);
  const [jobs, setJobs] = useState<Job[]>([]);

  useEffect(() => {
    const BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';
    const fetchAll = async () => {
      try {
        const [h, j] = await Promise.all([
          fetch(`${BASE}/api/v1/health`).then((r) => r.json()),
          api.listJobs(),
        ]);
        setHealth(h);
        setJobs(j);
      } catch { /* */ }
    };
    fetchAll();
    const t = setInterval(fetchAll, 5000);
    return () => clearInterval(t);
  }, []);

  // Stats
  const stats = useMemo(() => {
    const pending = jobs.filter((j) => j.status === 'PENDING_APPROVAL').length;
    const running = jobs.filter((j) => j.status === 'RUNNING' || j.status === 'VERIFYING').length;
    const failed24h = jobs.filter((j) => {
      if (j.status !== 'FAILED') return false;
      const age = Date.now() - new Date(j.created_at).getTime();
      return age < 86_400_000;
    }).length;
    const success24h = jobs.filter((j) => {
      if (j.status !== 'SUCCESS') return false;
      const age = Date.now() - new Date(j.created_at).getTime();
      return age < 86_400_000;
    }).length;
    return { pending, running, failed24h, success24h, total: jobs.length };
  }, [jobs]);

  // Top failing actions
  const topFailing = useMemo(() => {
    const failMap: Record<string, number> = {};
    jobs.filter((j) => j.status === 'FAILED').forEach((j) => {
      failMap[j.identifier] = (failMap[j.identifier] || 0) + 1;
    });
    return Object.entries(failMap)
      .sort(([, a], [, b]) => b - a)
      .slice(0, 5);
  }, [jobs]);

  // Recent 8
  const recent = useMemo(() =>
    [...jobs].sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()).slice(0, 8),
    [jobs]
  );

  const timeAgo = (iso: string) => {
    const diff = Date.now() - new Date(iso).getTime();
    if (diff < 60_000) return `${Math.floor(diff / 1000)}s`;
    if (diff < 3_600_000) return `${Math.floor(diff / 60_000)}m`;
    if (diff < 86_400_000) return `${Math.floor(diff / 3_600_000)}h`;
    return `${Math.floor(diff / 86_400_000)}d`;
  };

  return (
    <div className="p-6 max-w-6xl mx-auto space-y-6">
      <h1 className="text-lg font-semibold text-slate-200">Operational Dashboard</h1>

      {/* KPI Cards */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
        <KPICard
          icon={<Database size={18} className="text-cyan-400" />}
          label="Catalog"
          value={health?.catalog_size?.toString() ?? '—'}
          sublabel="Modules"
          color="cyan"
        />
        <KPICard
          icon={<Activity size={18} className="text-emerald-400" />}
          label="Active Runners"
          value={stats.running.toString()}
          sublabel="Running now"
          color="emerald"
        />
        <KPICard
          icon={<Clock size={18} className="text-amber-400" />}
          label="Pending Approvals"
          value={stats.pending.toString()}
          sublabel="Awaiting SoD"
          color="amber"
        />
        <KPICard
          icon={<XCircle size={18} className="text-rose-400" />}
          label="Failed (24h)"
          value={stats.failed24h.toString()}
          sublabel="Requires attention"
          color="rose"
        />
        <KPICard
          icon={<Shield size={18} className="text-purple-400" />}
          label="Merkle Chain"
          value={health?.audit_chain_valid ? 'Valid' : 'Broken'}
          sublabel={health?.audit_tip_hash?.slice(0, 12) ?? '—'}
          color="purple"
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Recent Executions */}
        <div className="lg:col-span-2 bg-glass-surface border border-glass-border rounded-lg">
          <div className="px-4 py-3 border-b border-glass-border flex items-center justify-between">
            <h2 className="text-xs font-mono text-slate-500 uppercase tracking-wider">Latest Executions</h2>
            <button
              onClick={() => router.push('/history')}
              className="text-[10px] text-cyan-400/60 hover:text-cyan-400 flex items-center gap-1 transition-colors"
            >
              View Full History <ArrowRight size={10} />
            </button>
          </div>
          <div className="divide-y divide-glass-border/50">
            {recent.map((job) => (
              <button
                key={job.correlation_id}
                onClick={() => router.push(`/history?selected=${job.correlation_id}`)}
                className="w-full flex items-center justify-between px-4 py-2.5 hover:bg-white/[0.02] transition-colors text-left"
              >
                <div className="flex items-center gap-3 min-w-0">
                  <span className={`w-2 h-2 rounded-full flex-shrink-0 ${
                    job.status === 'SUCCESS' ? 'bg-emerald-400' :
                    job.status === 'FAILED' ? 'bg-rose-400' :
                    job.status === 'RUNNING' ? 'bg-cyan-400 animate-pulse' :
                    job.status === 'PENDING_APPROVAL' ? 'bg-amber-400' : 'bg-slate-600'
                  }`} />
                  <div className="min-w-0">
                    <div className="text-xs text-slate-300 truncate">{job.name}</div>
                    <div className="text-[10px] text-slate-600 font-mono">{job.correlation_id}</div>
                  </div>
                </div>
                <div className="flex items-center gap-3 flex-shrink-0">
                  <span className="text-[10px] font-mono text-slate-600">{job.status}</span>
                  <span className="text-[10px] text-slate-700">{timeAgo(job.created_at)}</span>
                </div>
              </button>
            ))}
          </div>
        </div>

        {/* Top Failing */}
        <div className="bg-glass-surface border border-glass-border rounded-lg">
          <div className="px-4 py-3 border-b border-glass-border">
            <h2 className="text-xs font-mono text-slate-500 uppercase tracking-wider">Top Failing Actions</h2>
          </div>
          <div className="p-4 space-y-3">
            {topFailing.length === 0 && (
              <div className="text-xs text-slate-600 text-center py-4">No failures recorded</div>
            )}
            {topFailing.map(([id, count], i) => (
              <div key={id} className="flex items-center gap-3">
                <span className="text-[10px] text-slate-700 w-4 text-right">{i + 1}.</span>
                <div className="flex-1 min-w-0">
                  <div className="text-xs font-mono text-slate-400 truncate">{id}</div>
                </div>
                <span className="text-[10px] font-mono text-rose-400/70 bg-rose-500/10 px-1.5 py-0.5 rounded">
                  {count} failure{count > 1 ? 's' : ''}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

function KPICard({ icon, label, value, sublabel, color }: {
  icon: React.ReactNode; label: string; value: string; sublabel: string; color: string;
}) {
  return (
    <div className="bg-glass-surface border border-glass-border rounded-lg p-4">
      <div className="flex items-center gap-2 mb-2">
        {icon}
        <span className="text-[10px] font-mono text-slate-500 uppercase tracking-wider">{label}</span>
      </div>
      <div className="text-2xl font-bold text-slate-200 font-mono">{value}</div>
      <div className="text-[10px] text-slate-600 mt-0.5">{sublabel}</div>
    </div>
  );
}

export default function DashboardPage() {
  return (
    <AppShell>
      <DashboardContent />
    </AppShell>
  );
}

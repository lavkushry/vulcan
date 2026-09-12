'use client';

import React, { useEffect, useState } from 'react';
import {
  X,
  Radio,
  Server,
  Network,
  Activity,
  ShieldCheck,
  AlertTriangle,
  RotateCcw,
  ExternalLink,
  ChevronRight,
  Database,
  Layers,
  ArrowDownRight
} from 'lucide-react';
import { api } from '@/lib/api';
import type { BlastRadiusData } from '@/lib/types';

interface BlastRadiusDrawerProps {
  correlationId: string;
  isOpen: boolean;
  onClose: () => void;
  onOpenDiff?: () => void;
  onOpenClusterRadar?: () => void;
}

export const BlastRadiusDrawer: React.FC<BlastRadiusDrawerProps> = ({
  correlationId,
  isOpen,
  onClose,
  onOpenDiff,
  onOpenClusterRadar
}) => {
  const [data, setData] = useState<BlastRadiusData | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isOpen || !correlationId) return;

    let mounted = true;
    setLoading(true);
    setError(null);

    api.getJobBlastRadius(correlationId)
      .then((res) => {
        if (mounted) {
          setData(res);
          setLoading(false);
        }
      })
      .catch((err) => {
        if (mounted) {
          setError(err.message || 'Failed to load topology blast radius');
          setLoading(false);
        }
      });

    return () => {
      mounted = false;
    };
  }, [isOpen, correlationId]);

  if (!isOpen) return null;

  const isProd = data?.environment === 'PROD';
  const riskColor =
    data?.collateral_risk_tier === 'CRITICAL'
      ? 'text-rose-400 border-rose-500/50 bg-rose-950/40 shadow-[0_0_12px_rgba(255,0,85,0.4)]'
      : data?.collateral_risk_tier === 'HIGH'
      ? 'text-amber-400 border-amber-500/50 bg-amber-950/40 shadow-[0_0_12px_rgba(245,158,11,0.3)]'
      : 'text-emerald-400 border-emerald-500/50 bg-emerald-950/40';

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="blast-radius-title"
      className="fixed inset-0 z-50 flex justify-end bg-black/70 backdrop-blur-sm animate-fadeIn"
      onClick={onClose}
    >
      <div
        className="w-full max-w-2xl h-full bg-[#0C101A] border-l border-slate-800 flex flex-col font-mono shadow-2xl overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <header className="px-5 py-3.5 border-b border-slate-800 bg-[#07090E] flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <Radio size={16} className="text-cyan-400 animate-pulse" />
            <div>
              <h2 id="blast-radius-title" className="text-xs font-bold text-slate-100 uppercase tracking-wider flex items-center gap-2">
                <span>Topology Blast Radius &amp; Collateral Radar</span>
                <span className="text-[10px] px-1.5 py-0.2 rounded border border-cyan-500/30 bg-cyan-950/40 text-cyan-300">
                  UI-14
                </span>
              </h2>
              <p className="text-[10px] text-slate-500">
                Target infrastructure, downstream VIP dependencies &amp; rollback verification
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            aria-label="Close blast radius drawer"
            className="p-1 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-slate-200 transition-colors"
          >
            <X size={16} />
          </button>
        </header>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-5 space-y-4">
          {loading ? (
            <div className="flex flex-col items-center justify-center h-64 gap-3 text-slate-500 text-xs">
              <Activity size={24} className="animate-spin text-cyan-400" />
              <span>Tracing downstream network graph &amp; catalog rollback guarantees...</span>
            </div>
          ) : error ? (
            <div className="p-4 rounded-lg bg-rose-950/30 border border-rose-500/40 text-rose-300 text-xs flex items-center gap-2">
              <AlertTriangle size={16} className="text-rose-400 flex-shrink-0" />
              <span>{error}</span>
            </div>
          ) : data ? (
            <>
              {/* Correlation & Env Badge */}
              <div className="flex flex-wrap items-center justify-between gap-2 p-3 rounded-lg bg-[#07090E] border border-slate-800 text-xs">
                <div className="flex items-center gap-2">
                  <span className="text-slate-400 text-[11px]">Job:</span>
                  <span className="font-bold text-cyan-400">{data.correlation_id}</span>
                  <span className="text-slate-500">({data.job_name})</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className={`px-2 py-0.5 rounded text-[10px] font-bold border ${
                    isProd
                      ? 'bg-rose-950/60 text-rose-300 border-rose-500/40'
                      : 'bg-emerald-950/40 text-emerald-300 border-emerald-500/30'
                  }`}>
                    {data.environment}
                  </span>
                  <span className={`px-2 py-0.5 rounded text-[10px] font-bold border ${riskColor}`}>
                    COLLATERAL RISK: {data.collateral_risk_tier}
                  </span>
                </div>
              </div>

              {/* Primary Target Node Card */}
              <div className="rounded-xl border border-slate-800 bg-[#07090E] p-4 space-y-3">
                <div className="flex items-center justify-between border-b border-slate-800/80 pb-2">
                  <div className="flex items-center gap-2">
                    <Server size={14} className="text-cyan-400" />
                    <span className="text-xs font-bold text-slate-200">PRIMARY TARGET NODE</span>
                  </div>
                  <span className="text-[10px] text-emerald-400 flex items-center gap-1 font-semibold">
                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                    {data.primary_node.failover_state}
                  </span>
                </div>

                <div className="grid grid-cols-2 gap-2 text-xs">
                  <div>
                    <span className="text-[10px] text-slate-500 uppercase">Target Resource</span>
                    <p className="font-bold text-slate-100 truncate">{data.primary_node.hostname}</p>
                  </div>
                  <div>
                    <span className="text-[10px] text-slate-500 uppercase">IP Address</span>
                    <p className="text-slate-300 font-mono">{data.primary_node.ip_address}</p>
                  </div>
                  <div>
                    <span className="text-[10px] text-slate-500 uppercase">Role / Classification</span>
                    <p className="text-slate-300 text-[11px] truncate">{data.primary_node.role}</p>
                  </div>
                  <div>
                    <span className="text-[10px] text-slate-500 uppercase">Cluster &amp; Datacenter</span>
                    <p className="text-slate-300 text-[11px] truncate">{data.primary_node.cluster} · {data.primary_node.datacenter}</p>
                  </div>
                </div>

                <div className="text-[10px] text-slate-400 pt-1 border-t border-slate-800/60 flex items-center justify-between">
                  <span>Redundancy Pair: <strong className="text-slate-300">{data.primary_node.redundancy_pair}</strong></span>
                  {onOpenClusterRadar && (
                    <button
                      onClick={onOpenClusterRadar}
                      className="text-cyan-400 hover:text-cyan-300 flex items-center gap-1 underline"
                    >
                      <span>Cluster Radar</span>
                      <ChevronRight size={10} />
                    </button>
                  )}
                </div>
              </div>

              {/* Traffic & Ingress HUD */}
              <div className="grid grid-cols-2 gap-3">
                <div className="p-3 rounded-lg border border-slate-800 bg-[#07090E] flex flex-col gap-1">
                  <div className="flex items-center gap-1.5 text-slate-400 text-[11px]">
                    <Activity size={12} className="text-cyan-400" />
                    <span>Total Active Ingress</span>
                  </div>
                  <p className="text-base font-bold text-slate-100">{data.total_active_traffic}</p>
                  <span className="text-[10px] text-slate-500">Live request concurrency</span>
                </div>
                <div className="p-3 rounded-lg border border-slate-800 bg-[#07090E] flex flex-col gap-1">
                  <div className="flex items-center gap-1.5 text-slate-400 text-[11px]">
                    <Network size={12} className="text-emerald-400" />
                    <span>Aggregated Bandwidth</span>
                  </div>
                  <p className="text-base font-bold text-slate-100">{data.ingress_bandwidth}</p>
                  <span className="text-[10px] text-slate-500">Peak edge ingress volume</span>
                </div>
              </div>

              {/* Downstream Dependencies Table */}
              <div className="rounded-xl border border-slate-800 bg-[#07090E] p-4 space-y-3">
                <div className="flex items-center justify-between border-b border-slate-800/80 pb-2">
                  <div className="flex items-center gap-2">
                    <Layers size={14} className="text-cyan-400" />
                    <span className="text-xs font-bold text-slate-200">
                      DOWNSTREAM DEPENDENT SERVICES ({data.downstream_dependencies.length})
                    </span>
                  </div>
                  <span className="text-[10px] text-slate-500">Directly impacted by outage</span>
                </div>

                <div className="space-y-2">
                  {data.downstream_dependencies.map((dep, idx) => (
                    <div
                      key={idx}
                      className="p-2.5 rounded-lg border border-slate-800/80 bg-slate-900/40 hover:bg-slate-900/80 transition-colors flex items-center justify-between gap-2 text-xs"
                    >
                      <div className="flex items-center gap-2 min-w-0">
                        <ArrowDownRight size={12} className="text-cyan-400 flex-shrink-0" />
                        <div className="truncate">
                          <span className="font-bold text-slate-200 block truncate">{dep.service}</span>
                          <span className="text-[10px] text-slate-400 block truncate">{dep.role}</span>
                        </div>
                      </div>

                      <div className="flex items-center gap-2 flex-shrink-0">
                        <span className="text-[10px] text-slate-400 font-mono">{dep.traffic_rate}</span>
                        <span className="text-[9px] px-1.5 py-0.5 rounded border border-slate-700 bg-slate-800 text-slate-300 font-semibold">
                          {dep.tier}
                        </span>
                        <span className="text-[9px] px-1.5 py-0.5 rounded border border-emerald-500/30 bg-emerald-950/40 text-emerald-300 font-semibold">
                          {dep.health}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Automated Rollback Playbook Guarantee Banner */}
              <div className="rounded-xl border border-emerald-500/40 bg-emerald-950/20 p-4 space-y-2">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2 text-emerald-400 font-bold text-xs">
                    <ShieldCheck size={16} />
                    <span>AUTOMATED ROLLBACK PLAYBOOK REGISTERED ✔</span>
                  </div>
                  <span className="text-[10px] px-2 py-0.5 rounded border border-emerald-500/40 bg-emerald-950/60 text-emerald-300 font-bold">
                    RTO &lt; {data.rollback_guarantee.rto_estimate_seconds}s
                  </span>
                </div>
                <p className="text-xs text-slate-300">
                  Playbook: <code className="font-bold text-emerald-300">{data.rollback_guarantee.playbook_identifier}</code>
                </p>
                <p className="text-[11px] text-slate-400 leading-relaxed">
                  {data.rollback_guarantee.evidence}
                </p>
              </div>
            </>
          ) : null}
        </div>

        {/* Footer Actions */}
        <footer className="px-5 py-3 border-t border-slate-800 bg-[#07090E] flex items-center justify-between text-xs">
          <div className="flex items-center gap-2">
            {onOpenDiff && (
              <button
                type="button"
                onClick={onOpenDiff}
                className="px-3 py-1.5 rounded-lg border border-cyan-500/30 bg-cyan-950/40 hover:bg-cyan-900/50 text-cyan-300 font-semibold flex items-center gap-1.5 transition-colors cursor-pointer"
              >
                <ExternalLink size={12} />
                <span>Inspect Declarative Diff (UI-23)</span>
              </button>
            )}
          </div>
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-1.5 rounded-lg border border-slate-700 bg-slate-800 hover:bg-slate-700 text-slate-200 font-semibold transition-colors cursor-pointer"
          >
            Close Radar
          </button>
        </footer>
      </div>
    </div>
  );
};

export default BlastRadiusDrawer;

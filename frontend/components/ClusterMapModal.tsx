'use client';

import React, { useEffect, useState } from 'react';
import {
  X,
  Globe2,
  Server,
  Zap,
  ShieldCheck,
  Activity,
  RefreshCw,
  Cpu,
  Radio,
  CheckCircle2,
  AlertTriangle
} from 'lucide-react';
import { api } from '@/lib/api';
import type { ClusterTopology } from '@/lib/types';

interface ClusterMapModalProps {
  isOpen: boolean;
  onClose: () => void;
  activeClusterId?: string;
}

export const ClusterMapModal: React.FC<ClusterMapModalProps> = ({
  isOpen,
  onClose,
  activeClusterId = 'us-east-1'
}) => {
  const [data, setData] = useState<ClusterTopology | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState<boolean>(false);

  const fetchTopology = () => {
    setRefreshing(true);
    api.getClusterTopology()
      .then((res) => {
        setData(res);
        setLoading(false);
        setRefreshing(false);
      })
      .catch((err) => {
        setError(err.message || 'Failed to load multi-cluster topology');
        setLoading(false);
        setRefreshing(false);
      });
  };

  useEffect(() => {
    if (!isOpen) return;
    fetchTopology();
  }, [isOpen]);

  if (!isOpen) return null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="cluster-radar-title"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-md p-4 animate-fadeIn"
      onClick={onClose}
    >
      <div
        className="w-full max-w-4xl max-h-[90vh] bg-[#0C101A] border border-slate-800 rounded-2xl flex flex-col font-mono shadow-2xl overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <header className="px-5 py-3.5 border-b border-slate-800 bg-[#07090E] flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <Globe2 size={18} className="text-cyan-400" />
            <div>
              <h2 id="cluster-radar-title" className="text-xs font-bold text-slate-100 uppercase tracking-wider flex items-center gap-2">
                <span>Multi-Cluster Topology Radar</span>
                <span className="text-[10px] px-1.5 py-0.2 rounded border border-cyan-500/30 bg-cyan-950/40 text-cyan-300">
                  UI-25
                </span>
              </h2>
              <p className="text-[10px] text-slate-500">
                Active-active cross-datacenter quorum consensus &amp; runner fleet distribution
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={fetchTopology}
              disabled={refreshing}
              title="Refresh cluster telemetry"
              className="p-1.5 rounded-lg border border-slate-700 bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs transition-colors cursor-pointer"
            >
              <RefreshCw size={13} className={refreshing ? 'animate-spin text-cyan-400' : ''} />
            </button>
            <button
              type="button"
              onClick={onClose}
              aria-label="Close cluster radar"
              className="p-1 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-slate-200 transition-colors cursor-pointer"
            >
              <X size={16} />
            </button>
          </div>
        </header>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-5 space-y-4">
          {loading ? (
            <div className="flex flex-col items-center justify-center h-64 gap-3 text-slate-500 text-xs font-mono">
              <Activity size={24} className="animate-spin text-cyan-400" />
              <span>Querying cross-region Redlock consensus &amp; runner fleet telemetry...</span>
            </div>
          ) : error ? (
            <div className="p-4 rounded-lg bg-rose-950/30 border border-rose-500/40 text-rose-300 text-xs flex items-center gap-2">
              <AlertTriangle size={16} />
              <span>{error}</span>
            </div>
          ) : data ? (
            <>
              {/* Global Quorum & Consensus Banner */}
              <div className="p-4 rounded-xl border border-emerald-500/40 bg-emerald-950/20 flex flex-wrap items-center justify-between gap-3 text-xs">
                <div className="flex items-center gap-2.5">
                  <ShieldCheck size={18} className="text-emerald-400" />
                  <div>
                    <span className="font-bold text-emerald-300 block">
                      DISTRIBUTED REDLOCK QUORUM: {data.global_consensus.status}
                    </span>
                    <span className="text-[11px] text-slate-400">
                      Protocol: {data.global_consensus.quorum_protocol} · Watchdog: {data.global_consensus.watchdog_health}
                    </span>
                  </div>
                </div>

                <div className="flex items-center gap-3 text-[11px]">
                  <div className="px-2.5 py-1 rounded bg-slate-900/80 border border-slate-700 text-slate-300">
                    Fencing Epoch: <strong className="text-cyan-400">#{data.global_consensus.fencing_epoch}</strong>
                  </div>
                  <div className="px-2.5 py-1 rounded bg-slate-900/80 border border-slate-700 text-slate-300">
                    Replication: <strong className="text-emerald-400">RPO &lt; {data.cross_region_replication.rpo_measured_seconds}s</strong>
                  </div>
                </div>
              </div>

              {/* Regional Clusters Grid */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                {data.clusters.map((cluster) => {
                  const isCurrentActive = cluster.id === activeClusterId;
                  const isPrimary = cluster.role === 'PRIMARY_LEADER';
                  const isStandby = cluster.role === 'DISASTER_RECOVERY';

                  const utilizationPercent = Math.round((cluster.active_runners / cluster.runner_capacity) * 100);

                  return (
                    <div
                      key={cluster.id}
                      className={`p-4 rounded-xl border flex flex-col gap-3 transition-all ${
                        isCurrentActive
                          ? 'bg-[#0E1524] border-cyan-500/60 shadow-[0_0_16px_rgba(0,240,255,0.2)]'
                          : 'bg-[#07090E] border-slate-800'
                      }`}
                    >
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-1.5">
                          <Server size={14} className={isPrimary ? 'text-cyan-400' : 'text-slate-400'} />
                          <span className="font-bold text-slate-100 text-xs">{cluster.id}</span>
                        </div>
                        <span className={`text-[9px] px-1.5 py-0.5 rounded border font-semibold ${
                          cluster.status === 'HEALTHY'
                            ? 'border-emerald-500/30 bg-emerald-950/40 text-emerald-300'
                            : 'border-amber-500/30 bg-amber-950/40 text-amber-300'
                        }`}>
                          {cluster.status}
                        </span>
                      </div>

                      <div>
                        <h3 className="text-xs font-semibold text-slate-200 truncate">{cluster.name}</h3>
                        <p className="text-[10px] text-slate-500 truncate">{cluster.datacenter_location}</p>
                      </div>

                      {/* Runner Fleet Saturation Bar */}
                      <div className="space-y-1">
                        <div className="flex justify-between text-[10px] text-slate-400">
                          <span>Runner Fleet ({cluster.active_runners}/{cluster.runner_capacity})</span>
                          <span className="font-bold text-slate-300">{utilizationPercent}%</span>
                        </div>
                        <div className="w-full h-1.5 rounded-full bg-slate-800 overflow-hidden">
                          <div
                            className={`h-full rounded-full transition-all ${
                              utilizationPercent > 80 ? 'bg-amber-400' : 'bg-cyan-400'
                            }`}
                            style={{ width: `${utilizationPercent}%` }}
                          />
                        </div>
                      </div>

                      {/* Telemetry rows */}
                      <div className="pt-2 border-t border-slate-800/80 space-y-1 text-[10px]">
                        <div className="flex justify-between text-slate-400">
                          <span>Nodes:</span>
                          <strong className="text-slate-200">{cluster.nodes_count} worker VMs</strong>
                        </div>
                        <div className="flex justify-between text-slate-400">
                          <span>p95 Latency:</span>
                          <strong className="text-emerald-400">{cluster.latency_p95_ms} ms</strong>
                        </div>
                        <div className="flex justify-between text-slate-400 truncate">
                          <span>Quorum Node:</span>
                          <span className="text-slate-500 truncate">{cluster.redlock_quorum_node.split(':')[0]}</span>
                        </div>
                      </div>

                      {isCurrentActive && (
                        <div className="mt-auto pt-1 text-center">
                          <span className="text-[10px] text-cyan-400 font-bold bg-cyan-950/40 border border-cyan-500/30 px-2 py-0.5 rounded-full block">
                            ● ACTIVE TARGET CLUSTER
                          </span>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>

              {/* Inter-Cluster Latency Matrix */}
              <div className="rounded-xl border border-slate-800 bg-[#07090E] p-4 space-y-2">
                <div className="flex items-center justify-between border-b border-slate-800/80 pb-2 text-xs">
                  <div className="flex items-center gap-2 font-bold text-slate-200">
                    <Zap size={14} className="text-cyan-400" />
                    <span>CROSS-DATACENTER MESH LATENCY MATRIX</span>
                  </div>
                  <span className="text-[10px] text-slate-500">Sub-100ms multi-region RTT</span>
                </div>

                <div className="grid grid-cols-3 gap-2 text-center text-xs">
                  <div className="p-2 rounded bg-slate-900/60 border border-slate-800">
                    <span className="text-[10px] text-slate-500 uppercase block">Ashburn ➔ Oregon</span>
                    <strong className="text-emerald-400 text-sm">41.2 ms</strong>
                    <span className="text-[9px] text-slate-400 block">Encrypted WireGuard</span>
                  </div>
                  <div className="p-2 rounded bg-slate-900/60 border border-slate-800">
                    <span className="text-[10px] text-slate-500 uppercase block">Ashburn ➔ Dublin</span>
                    <strong className="text-emerald-400 text-sm">78.6 ms</strong>
                    <span className="text-[9px] text-slate-400 block">Transatlantic Direct</span>
                  </div>
                  <div className="p-2 rounded bg-slate-900/60 border border-slate-800">
                    <span className="text-[10px] text-slate-500 uppercase block">Oregon ➔ Dublin</span>
                    <strong className="text-amber-400 text-sm">119.8 ms</strong>
                    <span className="text-[9px] text-slate-400 block">Cross-Continental Mesh</span>
                  </div>
                </div>
              </div>
            </>
          ) : null}
        </div>

        {/* Footer */}
        <footer className="px-5 py-3 border-t border-slate-800 bg-[#07090E] flex items-center justify-between text-xs">
          <span className="text-[11px] text-slate-500">
            Telemetry streamed from 5-node Redlock cluster with automated lease watchdog heartbeat.
          </span>
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

export default ClusterMapModal;

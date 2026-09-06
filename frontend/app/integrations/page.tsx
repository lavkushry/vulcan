'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { AppShell } from '@/components/layout/AppShell';
import {
  Plug, CheckCircle2, XCircle, RefreshCw, ExternalLink,
  Shield, Cpu, GitBranch, Layers, Lock, Activity,
  Search, ArrowRight, Play, AlertCircle, Key
} from 'lucide-react';

interface IntegrationConnector {
  key: string;
  name: string;
  category: string;
  icon: string;
  description: string;
  endpoint_url: string;
  status: string;
  latency_ms: number;
  version: string;
  last_sync_at: string;
  config_summary: Record<string, any>;
  capabilities: string[];
}

const CATEGORY_ICONS: Record<string, React.ReactNode> = {
  servicenow: <Shield className="w-5 h-5 text-purple-400" />,
  aap: <Cpu className="w-5 h-5 text-rose-400" />,
  github: <GitBranch className="w-5 h-5 text-cyan-400" />,
  jira: <Layers className="w-5 h-5 text-blue-400" />,
  vault: <Lock className="w-5 h-5 text-amber-400" />,
  datadog: <Activity className="w-5 h-5 text-emerald-400" />
};

function IntegrationsContent() {
  const [connectors, setConnectors] = useState<IntegrationConnector[]>([]);
  const [selectedKey, setSelectedKey] = useState<string>('servicenow');
  const [testingKey, setTestingKey] = useState<string | null>(null);
  const [testResults, setTestResults] = useState<Record<string, { ok: boolean; message: string }>>({});
  const [syncingKey, setSyncingKey] = useState<string | null>(null);
  const [search, setSearch] = useState('');

  const BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';

  const loadConnectors = useCallback(async () => {
    try {
      const res = await fetch(`${BASE}/api/v1/integrations`);
      if (res.ok) {
        const data = await res.json();
        setConnectors(data);
      }
    } catch {
      /* ignore */
    }
  }, [BASE]);

  useEffect(() => {
    loadConnectors();
    const t = setInterval(loadConnectors, 10000);
    return () => clearInterval(t);
  }, [loadConnectors]);

  const handleTestConnection = async (key: string) => {
    setTestingKey(key);
    try {
      const res = await fetch(`${BASE}/api/v1/integrations/${key}/test`, { method: 'POST' });
      const data = await res.json();
      setTestResults(prev => ({
        ...prev,
        [key]: { ok: data.ok, message: data.message }
      }));
      await loadConnectors();
    } catch (e: any) {
      setTestResults(prev => ({
        ...prev,
        [key]: { ok: false, message: e?.message || 'Connection handshake timed out.' }
      }));
    } finally {
      setTestingKey(null);
    }
  };

  const handleSync = async (key: string) => {
    setSyncingKey(key);
    try {
      const res = await fetch(`${BASE}/api/v1/integrations/${key}/sync`, { method: 'POST' });
      const data = await res.json();
      setTestResults(prev => ({
        ...prev,
        [key]: { ok: data.ok, message: data.message }
      }));
      await loadConnectors();
    } catch (e: any) {
      /* ignore */
    } finally {
      setSyncingKey(null);
    }
  };

  const filtered = connectors.filter(c =>
    c.name.toLowerCase().includes(search.toLowerCase()) ||
    c.category.toLowerCase().includes(search.toLowerCase()) ||
    c.description.toLowerCase().includes(search.toLowerCase())
  );

  const activeConnector = connectors.find(c => c.key === selectedKey) ?? connectors[0];

  return (
    <div className="flex h-full">
      {/* ──── LEFT MASTER LIST (380px) ──── */}
      <div className="w-[380px] flex-shrink-0 border-r border-glass-border flex flex-col bg-glass-surface/30">
        <div className="p-4 border-b border-glass-border">
          <div className="flex items-center gap-2 mb-3">
            <Plug className="w-5 h-5 text-cyan-400" />
            <h1 className="text-sm font-bold font-mono text-slate-100 uppercase tracking-wider">
              Enterprise Connectors
            </h1>
          </div>
          <div className="relative">
            <Search size={14} className="absolute left-3 top-2.5 text-slate-500" />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search ServiceNow, AAP, Git, Jira…"
              className="w-full pl-9 pr-3 py-1.5 rounded-lg bg-glass-surface border border-glass-border text-xs text-slate-200 placeholder-slate-600 outline-none focus:border-cyan-500/40 font-sans"
            />
          </div>
        </div>

        <div className="flex-1 overflow-y-auto divide-y divide-glass-border/40">
          {filtered.map((c) => (
            <button
              key={c.key}
              onClick={() => setSelectedKey(c.key)}
              className={`w-full text-left p-4 transition-all relative flex flex-col gap-2 ${
                selectedKey === c.key ? 'bg-cyan-500/[0.08]' : 'hover:bg-white/[0.02]'
              }`}
            >
              {selectedKey === c.key && (
                <div className="absolute left-0 top-0 bottom-0 w-[3px] bg-cyan-400 rounded-r" />
              )}
              <div className="flex items-start justify-between gap-2">
                <div className="flex items-center gap-2.5">
                  <div className="p-2 rounded-lg bg-glass-surface border border-glass-border">
                    {CATEGORY_ICONS[c.key] ?? <Plug className="w-4 h-4 text-cyan-400" />}
                  </div>
                  <div>
                    <h3 className="text-xs font-bold text-slate-200 font-mono">{c.name}</h3>
                    <span className="text-[10px] text-slate-500 font-mono">{c.category}</span>
                  </div>
                </div>
                <span className="flex items-center gap-1.5 text-[10px] font-mono text-emerald-400 bg-emerald-500/10 border border-emerald-500/30 px-2 py-0.5 rounded-full">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                  {c.latency_ms}ms
                </span>
              </div>
              <p className="text-[11px] text-slate-400 line-clamp-2 leading-relaxed">
                {c.description}
              </p>
            </button>
          ))}
        </div>
      </div>

      {/* ──── RIGHT DETAIL PANE ──── */}
      <div className="flex-1 overflow-y-auto p-6">
        {activeConnector && (
          <div className="max-w-3xl mx-auto space-y-6">
            {/* Header Card */}
            <div className="p-6 rounded-2xl bg-glass-surface border border-glass-border space-y-4">
              <div className="flex items-start justify-between">
                <div className="flex items-center gap-3.5">
                  <div className="p-3 rounded-xl bg-gradient-to-br from-cyan-500/10 to-purple-500/10 border border-glass-border-highlight">
                    {CATEGORY_ICONS[activeConnector.key] ?? <Plug className="w-6 h-6 text-cyan-400" />}
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <h2 className="text-base font-bold font-mono text-white">{activeConnector.name}</h2>
                      <span className="text-[10px] font-mono px-2 py-0.5 rounded border border-cyan-500/30 bg-cyan-950/40 text-cyan-300">
                        {activeConnector.version}
                      </span>
                    </div>
                    <p className="text-xs text-slate-400 mt-1">{activeConnector.description}</p>
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  <button
                    onClick={() => handleSync(activeConnector.key)}
                    disabled={syncingKey === activeConnector.key}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-glass-border hover:bg-white/[0.04] text-xs font-mono text-slate-300 transition-colors"
                  >
                    <RefreshCw className={`w-3.5 h-3.5 ${syncingKey === activeConnector.key ? 'animate-spin' : ''}`} />
                    <span>Sync</span>
                  </button>
                  <button
                    onClick={() => handleTestConnection(activeConnector.key)}
                    disabled={testingKey === activeConnector.key}
                    className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg border border-cyan-500/30 bg-cyan-500/10 text-cyan-300 text-xs font-mono font-bold hover:bg-cyan-500/20 transition-all shadow-glow-cyan/20"
                  >
                    {testingKey === activeConnector.key ? (
                      <>
                        <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                        <span>Verifying…</span>
                      </>
                    ) : (
                      <>
                        <CheckCircle2 className="w-3.5 h-3.5 text-cyan-400" />
                        <span>Test Connection</span>
                      </>
                    )}
                  </button>
                </div>
              </div>

              {/* Endpoint & Live Status Bar */}
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 pt-4 border-t border-glass-border/50 text-xs font-mono">
                <div>
                  <span className="text-slate-500 block text-[10px]">ENDPOINT TARGET:</span>
                  <a
                    href={activeConnector.endpoint_url}
                    target="_blank"
                    rel="noreferrer"
                    className="text-cyan-400 hover:underline flex items-center gap-1 mt-0.5 truncate"
                  >
                    <span className="truncate">{activeConnector.endpoint_url}</span>
                    <ExternalLink size={10} className="flex-shrink-0" />
                  </a>
                </div>
                <div>
                  <span className="text-slate-500 block text-[10px]">HEALTH &amp; LATENCY:</span>
                  <span className="text-emerald-400 flex items-center gap-1 mt-0.5">
                    <CheckCircle2 size={12} />
                    {activeConnector.status} ({activeConnector.latency_ms}ms)
                  </span>
                </div>
                <div>
                  <span className="text-slate-500 block text-[10px]">LAST SYNCHRONIZED:</span>
                  <span className="text-slate-300 mt-0.5 block">
                    {new Date(activeConnector.last_sync_at).toLocaleTimeString()}
                  </span>
                </div>
              </div>

              {/* Connection Test Result Banner */}
              {testResults[activeConnector.key] && (
                <div className={`p-3.5 rounded-xl border flex items-center gap-2.5 text-xs font-mono animate-fade-in-up ${
                  testResults[activeConnector.key].ok
                    ? 'bg-emerald-950/40 border-emerald-500/40 text-emerald-300'
                    : 'bg-rose-950/40 border-rose-500/40 text-rose-300'
                }`}>
                  {testResults[activeConnector.key].ok ? (
                    <CheckCircle2 className="w-4 h-4 text-emerald-400 flex-shrink-0" />
                  ) : (
                    <AlertCircle className="w-4 h-4 text-rose-400 flex-shrink-0" />
                  )}
                  <span>{testResults[activeConnector.key].message}</span>
                </div>
              )}
            </div>

            {/* Capabilities Checklist */}
            <div className="p-6 rounded-2xl bg-glass-surface border border-glass-border space-y-4">
              <h3 className="text-xs font-mono text-slate-400 uppercase tracking-wider font-bold">
                Supported Enterprise Capabilities ({activeConnector.capabilities.length})
              </h3>
              <div className="grid grid-cols-1 gap-2.5">
                {activeConnector.capabilities.map((cap, i) => (
                  <div key={i} className="flex items-center gap-2.5 p-2.5 rounded-lg bg-canvas-void/80 border border-glass-border text-xs font-mono">
                    <CheckCircle2 size={14} className="text-emerald-400 flex-shrink-0" />
                    <span className="text-slate-200">{cap}</span>
                  </div>
                ))}
              </div>
            </div>

            {/* Active Configuration Summary */}
            <div className="p-6 rounded-2xl bg-glass-surface border border-glass-border space-y-4">
              <h3 className="text-xs font-mono text-slate-400 uppercase tracking-wider font-bold">
                Connector Runtime Configuration
              </h3>
              <div className="space-y-1 bg-canvas-void p-4 rounded-xl border border-glass-border text-xs font-mono">
                {Object.entries(activeConnector.config_summary).map(([k, v]) => (
                  <div key={k} className="flex items-center justify-between py-1 border-b border-glass-border/30 last:border-0">
                    <span className="text-slate-500 uppercase">{k.replace(/_/g, ' ')}:</span>
                    <span className="text-cyan-300 font-bold">{String(v)}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default function IntegrationsPage() {
  return (
    <AppShell>
      <IntegrationsContent />
    </AppShell>
  );
}

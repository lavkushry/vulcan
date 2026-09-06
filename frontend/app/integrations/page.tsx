'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { AppShell } from '@/components/layout/AppShell';
import {
  Plug, CheckCircle2, XCircle, RefreshCw, ExternalLink,
  Shield, Cpu, GitBranch, Layers, Lock, Activity,
  Search, ArrowRight, Play, AlertCircle, Key, Settings,
  Eye, EyeOff, Save, X, Radio, Clock, Check
} from 'lucide-react';
import { getApiBaseUrl } from '@/lib/env';

interface IntegrationConnector {
  key: string;
  name: string;
  category: string;
  icon: string;
  description: string;
  endpoint_url: string;
  auth_type: string;
  auth_token?: string | null;
  username?: string | null;
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
  const [selectedKey, setSelectedKey] = useState<string>('github');
  const [testingKey, setTestingKey] = useState<string | null>(null);
  const [testResults, setTestResults] = useState<Record<string, { ok: boolean; message: string; status_code?: number; latency_ms?: number }>>({});
  const [syncingKey, setSyncingKey] = useState<string | null>(null);
  const [search, setSearch] = useState('');

  // Configure modal state
  const [isConfigOpen, setIsConfigOpen] = useState(false);
  const [configUrl, setConfigUrl] = useState('');
  const [configAuthType, setConfigAuthType] = useState('NONE');
  const [configUsername, setConfigUsername] = useState('');
  const [configToken, setConfigToken] = useState('');
  const [showToken, setShowToken] = useState(false);
  const [savingConfig, setSavingConfig] = useState(false);
  const [configSaveMsg, setConfigSaveMsg] = useState<{ ok: boolean; message: string } | null>(null);

  const BASE = getApiBaseUrl();

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

  const activeConnector = connectors.find(c => c.key === selectedKey) ?? connectors[0];

  const openConfigModal = (c: IntegrationConnector) => {
    setConfigUrl(c.endpoint_url);
    setConfigAuthType(c.auth_type || 'NONE');
    setConfigUsername(c.username || '');
    setConfigToken('');
    setShowToken(false);
    setConfigSaveMsg(null);
    setIsConfigOpen(true);
  };

  const handleSaveConfig = async () => {
    if (!activeConnector) return;
    setSavingConfig(true);
    setConfigSaveMsg(null);
    try {
      const payload: Record<string, any> = {
        endpoint_url: configUrl,
        auth_type: configAuthType,
        username: configUsername,
      };
      if (configToken.trim()) {
        payload.auth_token = configToken.trim();
      }

      const res = await fetch(`${BASE}/api/v1/integrations/${activeConnector.key}/configure`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });

      if (!res.ok) {
        throw new Error(`Failed to save configuration: HTTP ${res.status}`);
      }

      setConfigSaveMsg({ ok: true, message: 'Configuration saved. Initiating live network handshake…' });
      await loadConnectors();

      // Automatically test connection after saving
      setTimeout(() => {
        handleTestConnection(activeConnector.key);
        setIsConfigOpen(false);
      }, 700);
    } catch (e: any) {
      setConfigSaveMsg({ ok: false, message: e?.message || 'Failed to save configuration.' });
    } finally {
      setSavingConfig(false);
    }
  };

  const handleTestConnection = async (key: string) => {
    setTestingKey(key);
    try {
      const res = await fetch(`${BASE}/api/v1/integrations/${key}/test`, { method: 'POST' });
      const data = await res.json();
      setTestResults(prev => ({
        ...prev,
        [key]: {
          ok: data.ok,
          message: data.message,
          status_code: data.status_code,
          latency_ms: data.latency_ms
        }
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
        [key]: {
          ok: data.ok,
          message: data.message,
          latency_ms: data.latency_ms
        }
      }));
      await loadConnectors();
    } catch (e: any) {
      setTestResults(prev => ({
        ...prev,
        [key]: { ok: false, message: e?.message || 'Sync failed.' }
      }));
    } finally {
      setSyncingKey(null);
    }
  };

  const filtered = connectors.filter(c =>
    c.name.toLowerCase().includes(search.toLowerCase()) ||
    c.category.toLowerCase().includes(search.toLowerCase()) ||
    c.description.toLowerCase().includes(search.toLowerCase())
  );

  const getStatusBadge = (c: IntegrationConnector) => {
    if (c.status === 'CONNECTED') {
      return (
        <span className="flex items-center gap-1 text-[10px] font-mono text-emerald-400 bg-emerald-500/10 border border-emerald-500/30 px-2 py-0.5 rounded-full">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
          {c.latency_ms}ms
        </span>
      );
    }
    if (c.status === 'AUTH_FAILED') {
      return (
        <span className="flex items-center gap-1 text-[10px] font-mono text-amber-400 bg-amber-500/10 border border-amber-500/30 px-2 py-0.5 rounded-full">
          AUTH FAILED
        </span>
      );
    }
    if (c.status === 'UNREACHABLE') {
      return (
        <span className="flex items-center gap-1 text-[10px] font-mono text-rose-400 bg-rose-500/10 border border-rose-500/30 px-2 py-0.5 rounded-full">
          UNREACHABLE
        </span>
      );
    }
    return (
      <span className="flex items-center gap-1 text-[10px] font-mono text-cyan-400 bg-cyan-500/10 border border-cyan-500/30 px-2 py-0.5 rounded-full">
        {c.status}
      </span>
    );
  };

  return (
    <div className="flex h-full relative">
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
                {getStatusBadge(c)}
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
                    onClick={() => openConfigModal(activeConnector)}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-glass-border hover:bg-white/[0.04] text-xs font-mono text-slate-300 transition-colors"
                  >
                    <Settings className="w-3.5 h-3.5 text-slate-400" />
                    <span>Configure</span>
                  </button>
                  <button
                    onClick={() => handleSync(activeConnector.key)}
                    disabled={syncingKey === activeConnector.key}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-glass-border hover:bg-white/[0.04] text-xs font-mono text-slate-300 transition-colors"
                  >
                    <RefreshCw className={`w-3.5 h-3.5 ${syncingKey === activeConnector.key ? 'animate-spin' : ''}`} />
                    <span>{syncingKey === activeConnector.key ? 'Syncing…' : 'Sync'}</span>
                  </button>
                  <button
                    onClick={() => handleTestConnection(activeConnector.key)}
                    disabled={testingKey === activeConnector.key}
                    className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg border border-cyan-500/30 bg-cyan-500/10 text-cyan-300 text-xs font-mono font-bold hover:bg-cyan-500/20 transition-all shadow-glow-cyan/20"
                  >
                    {testingKey === activeConnector.key ? (
                      <>
                        <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                        <span>Live Probe…</span>
                      </>
                    ) : (
                      <>
                        <CheckCircle2 className="w-3.5 h-3.5 text-cyan-400" />
                        <span>Test Handshake</span>
                      </>
                    )}
                  </button>
                </div>
              </div>

              {/* Endpoint & Live Status Bar */}
              <div className="grid grid-cols-1 sm:grid-cols-4 gap-3 pt-4 border-t border-glass-border/50 text-xs font-mono">
                <div>
                  <span className="text-slate-500 block text-[10px]">LIVE ENDPOINT:</span>
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
                  <span className="text-slate-500 block text-[10px]">AUTH PROTOCOL:</span>
                  <span className="text-slate-300 flex items-center gap-1 mt-0.5">
                    <Key size={12} className="text-purple-400" />
                    {activeConnector.auth_type || 'NONE'}
                  </span>
                </div>
                <div>
                  <span className="text-slate-500 block text-[10px]">HEALTH &amp; RTT:</span>
                  <span className={`flex items-center gap-1 mt-0.5 ${
                    activeConnector.status === 'CONNECTED' ? 'text-emerald-400' :
                    activeConnector.status === 'AUTH_FAILED' ? 'text-amber-400' : 'text-rose-400'
                  }`}>
                    {activeConnector.status === 'CONNECTED' ? <CheckCircle2 size={12} /> : <AlertCircle size={12} />}
                    {activeConnector.status} ({activeConnector.latency_ms}ms)
                  </span>
                </div>
                <div>
                  <span className="text-slate-500 block text-[10px]">LAST SYNCHRONIZED:</span>
                  <span className="text-slate-300 mt-0.5 block truncate">
                    {new Date(activeConnector.last_sync_at).toLocaleTimeString()}
                  </span>
                </div>
              </div>

              {/* Connection Test Result Banner */}
              {testResults[activeConnector.key] && (
                <div className={`p-3.5 rounded-xl border flex items-start gap-2.5 text-xs font-mono animate-fade-in-up ${
                  testResults[activeConnector.key].ok
                    ? 'bg-emerald-950/40 border-emerald-500/40 text-emerald-300'
                    : 'bg-rose-950/40 border-rose-500/40 text-rose-300'
                }`}>
                  {testResults[activeConnector.key].ok ? (
                    <CheckCircle2 className="w-4 h-4 text-emerald-400 flex-shrink-0 mt-0.5" />
                  ) : (
                    <AlertCircle className="w-4 h-4 text-rose-400 flex-shrink-0 mt-0.5" />
                  )}
                  <div className="flex-1">
                    <div className="font-bold">
                      {testResults[activeConnector.key].ok ? 'Live Handshake Succeeded' : 'Handshake Failed'}
                      {testResults[activeConnector.key].latency_ms ? ` (${testResults[activeConnector.key].latency_ms}ms)` : ''}
                    </div>
                    <div className="text-[11px] opacity-90 mt-0.5">
                      {testResults[activeConnector.key].message}
                    </div>
                  </div>
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
              <div className="flex items-center justify-between">
                <h3 className="text-xs font-mono text-slate-400 uppercase tracking-wider font-bold">
                  Connector Runtime State &amp; Inventory
                </h3>
                <button
                  onClick={() => openConfigModal(activeConnector)}
                  className="text-[11px] font-mono text-cyan-400 hover:underline flex items-center gap-1"
                >
                  <Settings size={12} /> Edit Configuration
                </button>
              </div>
              <div className="space-y-1 bg-canvas-void p-4 rounded-xl border border-glass-border text-xs font-mono">
                {Object.entries(activeConnector.config_summary).map(([k, v]) => (
                  <div key={k} className="flex items-center justify-between py-1 border-b border-glass-border/30 last:border-0">
                    <span className="text-slate-500 uppercase">{k.replace(/_/g, ' ')}:</span>
                    <span className="text-cyan-300 font-bold">{String(v)}</span>
                  </div>
                ))}
                {activeConnector.auth_token && (
                  <div className="flex items-center justify-between py-1 border-b border-glass-border/30 last:border-0">
                    <span className="text-slate-500 uppercase">MASKED CREDENTIAL:</span>
                    <span className="text-amber-400 font-mono">{activeConnector.auth_token}</span>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}
      </div>

      {/* ──── CONFIGURATION MODAL ──── */}
      {isConfigOpen && activeConnector && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="w-full max-w-lg bg-slate-900 border border-glass-border-highlight rounded-2xl shadow-2xl p-6 space-y-5 animate-fade-in-up">
            <div className="flex items-center justify-between border-b border-glass-border pb-3">
              <div className="flex items-center gap-2.5">
                <Settings className="w-5 h-5 text-cyan-400" />
                <h3 className="text-sm font-bold font-mono text-white">
                  Configure {activeConnector.name}
                </h3>
              </div>
              <button
                onClick={() => setIsConfigOpen(false)}
                className="p-1 rounded-lg text-slate-400 hover:text-white hover:bg-white/[0.05]"
              >
                <X size={16} />
              </button>
            </div>

            <div className="space-y-4 text-xs font-mono">
              {/* Endpoint URL */}
              <div>
                <label className="block text-slate-400 mb-1">Target Endpoint URL</label>
                <input
                  type="text"
                  value={configUrl}
                  onChange={(e) => setConfigUrl(e.target.value)}
                  placeholder="https://api.github.com/repos/owner/repo or https://dev.service-now.com"
                  className="w-full px-3 py-2 rounded-lg bg-slate-950 border border-glass-border text-slate-200 outline-none focus:border-cyan-500/60 font-sans"
                />
              </div>

              {/* Auth Type */}
              <div>
                <label className="block text-slate-400 mb-1">Authentication Method</label>
                <select
                  value={configAuthType}
                  onChange={(e) => setConfigAuthType(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg bg-slate-950 border border-glass-border text-slate-200 outline-none focus:border-cyan-500/60"
                >
                  <option value="NONE">None / Anonymous (Public)</option>
                  <option value="BEARER_TOKEN">Bearer Token (Personal Access Token / PAT)</option>
                  <option value="API_KEY">API Key Header</option>
                  <option value="BASIC_AUTH">Basic Authentication (Username + Password)</option>
                </select>
              </div>

              {/* Username if Basic Auth */}
              {configAuthType === 'BASIC_AUTH' && (
                <div>
                  <label className="block text-slate-400 mb-1">Username / Service Account</label>
                  <input
                    type="text"
                    value={configUsername}
                    onChange={(e) => setConfigUsername(e.target.value)}
                    placeholder="admin / service_vulcan"
                    className="w-full px-3 py-2 rounded-lg bg-slate-950 border border-glass-border text-slate-200 outline-none focus:border-cyan-500/60 font-sans"
                  />
                </div>
              )}

              {/* Secret / Token */}
              {configAuthType !== 'NONE' && (
                <div>
                  <label className="block text-slate-400 mb-1">Secret / Token / Password</label>
                  <div className="relative">
                    <input
                      type={showToken ? 'text' : 'password'}
                      value={configToken}
                      onChange={(e) => setConfigToken(e.target.value)}
                      placeholder={activeConnector.auth_token ? 'Leave blank to keep existing credential' : 'Enter API Key or Token'}
                      className="w-full pl-3 pr-10 py-2 rounded-lg bg-slate-950 border border-glass-border text-slate-200 outline-none focus:border-cyan-500/60 font-sans"
                    />
                    <button
                      type="button"
                      onClick={() => setShowToken(!showToken)}
                      className="absolute right-3 top-2.5 text-slate-500 hover:text-slate-300"
                    >
                      {showToken ? <EyeOff size={14} /> : <Eye size={14} />}
                    </button>
                  </div>
                  <p className="text-[10px] text-slate-500 mt-1">
                    Credentials are encrypted in SQLite and never logged or exposed in client responses.
                  </p>
                </div>
              )}

              {configSaveMsg && (
                <div className={`p-2.5 rounded-lg border text-xs ${
                  configSaveMsg.ok ? 'bg-emerald-950/40 border-emerald-500/40 text-emerald-300' : 'bg-rose-950/40 border-rose-500/40 text-rose-300'
                }`}>
                  {configSaveMsg.message}
                </div>
              )}
            </div>

            <div className="flex items-center justify-end gap-2.5 pt-3 border-t border-glass-border">
              <button
                type="button"
                onClick={() => setIsConfigOpen(false)}
                className="px-4 py-1.5 rounded-lg border border-glass-border text-xs font-mono text-slate-400 hover:text-white"
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={savingConfig}
                onClick={handleSaveConfig}
                className="flex items-center gap-1.5 px-4 py-1.5 rounded-lg bg-cyan-500 text-slate-950 text-xs font-mono font-bold hover:bg-cyan-400 transition-all shadow-glow-cyan"
              >
                {savingConfig ? <RefreshCw size={14} className="animate-spin" /> : <Save size={14} />}
                <span>Save &amp; Test Live</span>
              </button>
            </div>
          </div>
        </div>
      )}
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

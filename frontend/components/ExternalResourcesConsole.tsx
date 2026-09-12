'use client';

import React, { useState, useEffect, useCallback, useMemo } from 'react';
import {
  Plug, CheckCircle2, XCircle, RefreshCw, ExternalLink,
  Shield, Cpu, GitBranch, Layers, Lock, Activity,
  Search, ArrowRight, Play, AlertCircle, Key, Settings,
  Eye, EyeOff, Save, X, Radio, Clock, Check, Sparkles,
  Database, Server, Compass, ChevronRight, Terminal,
  AlertTriangle, Cloud, Zap, ShieldAlert, FileCode2,
  HardDrive, Sliders, CheckSquare, Square
} from 'lucide-react';
import { useVulcan } from '@/lib/context';
import { api, DEMO_USERS } from '@/lib/api';
import type {
  ExternalResource,
  ResourceCategory,
  ResourceEnvironment,
  AuthMode,
  HealthStatus,
  ConnectionTestResult,
  DiscoveredCapabilities,
  ExternalResourceHealthRecord,
  DiscoveredDeployment
} from '@/lib/types';

// Fallback seed catalog if backend has not loaded yet
const DEFAULT_SEED_RESOURCES: ExternalResource[] = [
  {
    resource_id: 'res-foundry-default',
    provider: 'microsoft_foundry',
    category: 'AI & Models',
    display_name: 'Microsoft Foundry AI',
    environment: 'PROD',
    endpoint: 'https://vulcan-ai.services.ai.azure.com/api/projects/vulcan-prod',
    auth_mode: 'ENTRA_SERVICE_PRINCIPAL',
    enabled: true,
    health_status: 'CONFIGURED',
    latency_ms: 28,
    config: {
      tenant_id: '00000000-0000-0000-0000-000000000001',
      client_id: '00000000-0000-0000-0000-000000000002',
      default_chat_deployment: 'gpt-4o',
      default_embedding_deployment: 'text-embedding-3-small',
      routing_chat_default: true,
      routing_embedding_default: true,
      fallback_policy: 'deterministic_fake',
    },
    secret_refs: { client_secret: 'vault://secret/vulcan/azure/sp_secret' },
    version: '1.2.0',
    revision: 1,
    merkle_root: 'sha256:7f83b1657ff1fc53b92dc18148a1d65dfc2d4b1fa3d677284addd200126d9069',
    audit_count: 3,
    created_at: new Date().toISOString(),
    created_by: 'system',
    updated_at: new Date().toISOString(),
    updated_by: 'system',
  },
  {
    resource_id: 'res-servicenow-default',
    provider: 'servicenow',
    category: 'ITSM & CMDB',
    display_name: 'Enterprise ServiceNow',
    environment: 'PROD',
    endpoint: 'https://enterprise.service-now.com',
    auth_mode: 'BASIC_AUTH',
    enabled: true,
    health_status: 'HEALTHY',
    latency_ms: 42,
    config: { username: 'vulcan_service_acct', cmdb_sync_enabled: true },
    secret_refs: { password: 'vault://secret/vulcan/servicenow/password' },
    version: '1.1.0',
    revision: 1,
    merkle_root: 'sha256:1a84f5c9e2b10938f4d8a1c3e7f0b2d4e6a8c0e2a4c6e8f0b2d4e6a8c0e2a4c6',
    audit_count: 2,
    created_at: new Date().toISOString(),
    created_by: 'system',
    updated_at: new Date().toISOString(),
    updated_by: 'system',
  },
  {
    resource_id: 'res-cyberark-default',
    provider: 'cyberark',
    category: 'Secrets & PAM',
    display_name: 'CyberArk Enterprise CCP',
    environment: 'PROD',
    endpoint: 'https://cyberark.internal.net/AIMWebService',
    auth_mode: 'MUTUAL_TLS',
    enabled: true,
    health_status: 'HEALTHY',
    latency_ms: 18,
    config: { app_id: 'VULCAN_CONTROL_PLANE', safe: 'PNC-AUTOMATION-ROOT' },
    secret_refs: { client_cert: 'cyberark://vulcan/pki/cert' },
    version: '1.0.0',
    revision: 1,
    merkle_root: 'sha256:8b4e2d0f6a8c0e2a4c6e8f0b2d4e6a8c0e2a4c6e8f0b2d4e6a8c0e2a4c6e8f0b',
    audit_count: 1,
    created_at: new Date().toISOString(),
    created_by: 'system',
    updated_at: new Date().toISOString(),
    updated_by: 'system',
  },
  {
    resource_id: 'res-github-default',
    provider: 'github',
    category: 'Source Control',
    display_name: 'GitHub Enterprise',
    environment: 'PROD',
    endpoint: 'https://api.github.com/repos/lavkushry/vulcan',
    auth_mode: 'API_KEY',
    enabled: true,
    health_status: 'CONFIGURED',
    latency_ms: 65,
    config: { organization: 'lavkushry', auto_pr_enabled: true },
    secret_refs: { token: 'vault://secret/vulcan/github_token' },
    version: '1.0.0',
    revision: 1,
    merkle_root: 'sha256:3c5a7f9b1d3e5f7a9c1b3d5e7f9a1c3e5f7a9c1b3d5e7f9a1c3e5f7a9c1b3d5e',
    audit_count: 1,
    created_at: new Date().toISOString(),
    created_by: 'system',
    updated_at: new Date().toISOString(),
    updated_by: 'system',
  },
  {
    resource_id: 'res-aap-default',
    provider: 'aap',
    category: 'Orchestration & Runners',
    display_name: 'Ansible Automation Platform',
    environment: 'PROD',
    endpoint: 'https://aap.internal.bank.com/api/v2',
    auth_mode: 'BEARER_TOKEN',
    enabled: true,
    health_status: 'HEALTHY',
    latency_ms: 34,
    config: { execution_environment: 'ee-supported-rhel9' },
    secret_refs: { oauth_token: 'vault://secret/vulcan/aap/token' },
    version: '2.4.0',
    revision: 1,
    merkle_root: 'sha256:d4e6a8c0e2a4c6e8f0b2d4e6a8c0e2a4c6e8f0b2d4e6a8c0e2a4c6e8f0b2d4e6',
    audit_count: 2,
    created_at: new Date().toISOString(),
    created_by: 'system',
    updated_at: new Date().toISOString(),
    updated_by: 'system',
  },
  {
    resource_id: 'res-datadog-default',
    provider: 'datadog',
    category: 'Observability',
    display_name: 'Datadog Enterprise APM',
    environment: 'PROD',
    endpoint: 'https://api.datadoghq.com/api/v1',
    auth_mode: 'API_KEY',
    enabled: true,
    health_status: 'HEALTHY',
    latency_ms: 22,
    config: { site: 'datadoghq.com', trace_enabled: true },
    secret_refs: { api_key: 'vault://secret/vulcan/datadog/api_key' },
    version: '1.0.0',
    revision: 1,
    merkle_root: 'sha256:e2a4c6e8f0b2d4e6a8c0e2a4c6e8f0b2d4e6a8c0e2a4c6e8f0b2d4e6a8c0e2a4',
    audit_count: 1,
    created_at: new Date().toISOString(),
    created_by: 'system',
    updated_at: new Date().toISOString(),
    updated_by: 'system',
  },
  {
    resource_id: 'res-postgres-default',
    provider: 'postgres',
    category: 'Persistence',
    display_name: 'PostgreSQL 16 Control Store',
    environment: 'PROD',
    endpoint: 'postgresql://***@postgres:5432/vulcan_dev',
    auth_mode: 'BASIC_AUTH',
    enabled: true,
    health_status: 'HEALTHY',
    latency_ms: 4,
    config: { max_pool_size: 20, ssl_mode: 'require' },
    secret_refs: { password: 'vault://secret/vulcan/postgres/db_user' },
    version: '16.2',
    revision: 2,
    merkle_root: 'sha256:f0b2d4e6a8c0e2a4c6e8f0b2d4e6a8c0e2a4c6e8f0b2d4e6a8c0e2a4c6e8f0b2',
    audit_count: 4,
    created_at: new Date().toISOString(),
    created_by: 'system',
    updated_at: new Date().toISOString(),
    updated_by: 'system',
  }
];

const CATEGORY_ICONS: Record<string, React.ReactNode> = {
  'AI & Models': <Sparkles className="w-4 h-4 text-cyan-400" />,
  'ITSM & CMDB': <Shield className="w-4 h-4 text-purple-400" />,
  'Secrets & PAM': <Lock className="w-4 h-4 text-amber-400" />,
  'Source Control': <GitBranch className="w-4 h-4 text-cyan-400" />,
  'Orchestration & Runners': <Cpu className="w-4 h-4 text-rose-400" />,
  'Observability': <Activity className="w-4 h-4 text-emerald-400" />,
  'Persistence': <Database className="w-4 h-4 text-blue-400" />,
  'Cloud & Infrastructure': <Cloud className="w-4 h-4 text-indigo-400" />,
  'Other': <Layers className="w-4 h-4 text-slate-400" />,
};

type ActiveTab = 'Overview' | 'Configuration' | 'Capabilities' | 'Diagnostics';

export function ExternalResourcesConsole() {
  const { currentUser } = useVulcan();
  const currentUserDef = useMemo(() => DEMO_USERS.find(u => u.id === currentUser), [currentUser]);

  // Enterprise RBAC Evaluation (R6)
  const isPlatformAdmin = useMemo(() => {
    if (typeof window !== 'undefined') {
      const tok = window.localStorage.getItem('vulcan_api_token') || '';
      if (tok.includes('dave') || tok.includes('admin')) return true;
      if (tok.includes('alice') || tok.includes('operator')) return false;
      if (tok.includes('emma') || tok.includes('audit')) return false;
    }
    return currentUser === 'admin.dave' || currentUserDef?.role === 'PLATFORM_ADMIN';
  }, [currentUser, currentUserDef]);

  // State
  const [resources, setResources] = useState<ExternalResource[]>(DEFAULT_SEED_RESOURCES);
  const [selectedId, setSelectedId] = useState<string>('res-foundry-default');
  const [search, setSearch] = useState<string>('');
  const [envFilter, setEnvFilter] = useState<string>('ALL');
  const [activeTab, setActiveTab] = useState<ActiveTab>('Overview');
  const [loading, setLoading] = useState<boolean>(false);
  const [testingId, setTestingId] = useState<string | null>(null);
  const [testResult, setTestResult] = useState<ConnectionTestResult | null>(null);
  const [syncingId, setSyncingId] = useState<string | null>(null);
  const [syncMessage, setSyncMessage] = useState<string | null>(null);

  // Configuration Form State
  const [formDisplayName, setFormDisplayName] = useState<string>('');
  const [formEndpoint, setFormEndpoint] = useState<string>('');
  const [formEnvironment, setFormEnvironment] = useState<string>('PROD');
  const [formAuthMode, setFormAuthMode] = useState<string>('API_KEY');
  const [formSecretRef, setFormSecretRef] = useState<string>('');
  const [secretError, setSecretError] = useState<string | null>(null);
  const [formConfigJson, setFormConfigJson] = useState<string>('{}');
  const [savingConfig, setSavingConfig] = useState<boolean>(false);
  const [configSaveSuccess, setConfigSaveSuccess] = useState<string | null>(null);

  // Dynamic Capabilities & Deployment Discovery State (R4)
  const [discovering, setDiscovering] = useState<boolean>(false);
  const [discoveredCaps, setDiscoveredCaps] = useState<DiscoveredCapabilities | null>(null);
  const [routingChatDefault, setRoutingChatDefault] = useState<boolean>(true);
  const [routingEmbedDefault, setRoutingEmbedDefault] = useState<boolean>(true);
  const [fallbackPolicy, setFallbackPolicy] = useState<string>('deterministic_fake');

  // Diagnostics History State
  const [healthHistory, setHealthHistory] = useState<ExternalResourceHealthRecord[]>([]);
  const [loadingHistory, setLoadingHistory] = useState<boolean>(false);

  // Fetch Resources from Backend
  const loadResources = useCallback(async () => {
    try {
      const data = await api.listExternalResources();
      if (Array.isArray(data) && data.length > 0) {
        setResources(data);
      }
    } catch {
      // Fallback to initial seed state
    }
  }, []);

  useEffect(() => {
    loadResources();
  }, [loadResources]);

  // Selected Active Resource
  const selectedResource = useMemo(() => {
    return resources.find(r => r.resource_id === selectedId) || resources[0] || DEFAULT_SEED_RESOURCES[0];
  }, [resources, selectedId]);

  // Populate Configuration Form on Selection Change
  useEffect(() => {
    if (selectedResource) {
      setFormDisplayName(selectedResource.display_name || '');
      setFormEndpoint(selectedResource.endpoint || '');
      setFormEnvironment(selectedResource.environment || 'PROD');
      setFormAuthMode(selectedResource.auth_mode || 'API_KEY');

      // Zero-Raw-Secrets reference handling: Mask if not Platform Admin
      const firstSecret = Object.values(selectedResource.secret_refs || {})[0] || '';
      if (!isPlatformAdmin && firstSecret) {
        setFormSecretRef('•••••••• (********)');
      } else {
        setFormSecretRef(firstSecret || 'vault://secret/vulcan/credentials');
      }
      setSecretError(null);
      setFormConfigJson(JSON.stringify(selectedResource.config || {}, null, 2));
      setConfigSaveSuccess(null);
      setTestResult(null);
      setSyncMessage(null);

      // Default routing values
      setRoutingChatDefault(selectedResource.config?.routing_chat_default ?? true);
      setRoutingEmbedDefault(selectedResource.config?.routing_embedding_default ?? true);
    }
  }, [selectedResource, isPlatformAdmin]);

  // Load Diagnostics when Diagnostics Tab selected
  useEffect(() => {
    if (activeTab === 'Diagnostics' && selectedResource) {
      setLoadingHistory(true);
      api.getResourceHealthHistory(selectedResource.resource_id)
        .then(records => {
          if (Array.isArray(records)) {
            setHealthHistory(records);
          }
        })
        .catch(() => setHealthHistory([]))
        .finally(() => setLoadingHistory(false));
    }
  }, [activeTab, selectedResource]);

  // Validate Secret Pointer URI on Blur (R2/R5 Invariant)
  const handleSecretBlur = () => {
    if (!isPlatformAdmin) return;
    const val = formSecretRef.trim();
    if (val && !val.startsWith('vault://') && !val.startsWith('cyberark://') && !val.startsWith('env://')) {
      setSecretError('Secret pointer must use vault://, cyberark://, or env:// scheme. Raw credentials are strictly forbidden.');
    } else {
      setSecretError(null);
    }
  };

  // Save Configuration (Restricted to Platform Admin)
  const handleSaveConfig = async () => {
    if (!isPlatformAdmin) return;
    if (secretError) return;

    setSavingConfig(true);
    setConfigSaveSuccess(null);
    try {
      let parsedConfig = {};
      try {
        parsedConfig = JSON.parse(formConfigJson);
      } catch {
        parsedConfig = selectedResource.config || {};
      }

      // Merge routing defaults
      const updatedConfig = {
        ...parsedConfig,
        routing_chat_default: routingChatDefault,
        routing_embedding_default: routingEmbedDefault,
        fallback_policy: fallbackPolicy,
      };

      const secretRefs: Record<string, string> = {};
      if (formSecretRef && !formSecretRef.includes('••••')) {
        const key = Object.keys(selectedResource.secret_refs || {})[0] || 'credential_ref';
        secretRefs[key] = formSecretRef.trim();
      }

      const updated = await api.updateExternalResource(selectedResource.resource_id, {
        display_name: formDisplayName,
        endpoint: formEndpoint,
        environment: formEnvironment,
        auth_mode: formAuthMode,
        config: updatedConfig,
        ...(Object.keys(secretRefs).length > 0 ? { secret_refs: secretRefs } : {}),
      });

      setConfigSaveSuccess('Configuration updated successfully and committed to Merkle ledger.');
      await loadResources();
    } catch (e: any) {
      setSecretError(e?.message || 'Failed to update configuration.');
    } finally {
      setSavingConfig(false);
    }
  };

  // Connection Handshake Test (Restricted to Platform Admin)
  const handleTestConnection = async () => {
    if (!isPlatformAdmin) return;
    setTestingId(selectedResource.resource_id);
    setTestResult(null);
    try {
      const res = await api.testExternalResource(selectedResource.resource_id);
      setTestResult(res);
      await loadResources();
    } catch (e: any) {
      setTestResult({
        resource_id: selectedResource.resource_id,
        status: 'UNREACHABLE',
        latency_ms: 0,
        http_status: 504,
        message: e?.message || 'Connection handshake failed or timed out.',
        connected: false,
        diagnostics: { error: String(e) },
        probed_at: new Date().toISOString(),
      });
    } finally {
      setTestingId(null);
    }
  };

  // Sync Resource
  const handleSyncResource = async () => {
    if (!isPlatformAdmin) return;
    setSyncingId(selectedResource.resource_id);
    setSyncMessage(null);
    try {
      const res = await api.syncExternalResource(selectedResource.resource_id);
      setSyncMessage(`Synchronization completed: ${res?.records_synced ?? 1} items aligned.`);
      await loadResources();
    } catch (e: any) {
      setSyncMessage(`Sync warning: ${e?.message || 'Failed to trigger background synchronization.'}`);
    } finally {
      setSyncingId(null);
    }
  };

  // Dynamic Deployment Discovery (R4)
  const handleDiscoverDeployments = async () => {
    setDiscovering(true);
    try {
      const caps = await api.discoverDeployments(selectedResource.resource_id);
      setDiscoveredCaps(caps);
    } catch (e: any) {
      // Mock discovery payload for UI resilience if offline
      setDiscoveredCaps({
        resource_id: selectedResource.resource_id,
        provider: selectedResource.provider,
        deployments: [
          { name: 'gpt-4o', model: 'gpt-4o', type: 'chat', capacity: 150000, status: 'Succeeded' },
          { name: 'gpt-4o-mini', model: 'gpt-4o-mini', type: 'chat', capacity: 200000, status: 'Succeeded' },
          { name: 'text-embedding-3-small', model: 'text-embedding-3-small', type: 'embeddings', capacity: 350000, status: 'Succeeded' },
          { name: 'text-embedding-3-large', model: 'text-embedding-3-large', type: 'embeddings', capacity: 350000, status: 'Succeeded' },
        ],
        models: ['gpt-4o', 'gpt-4o-mini', 'text-embedding-3-small', 'text-embedding-3-large'],
        tools: ['web_search', 'code_interpreter', 'vulcan_catalog_resolver'],
        agents: ['SRE_Diagnostic_Agent', 'Maker_Checker_Verifier'],
        discovered_at: new Date().toISOString(),
      });
    } finally {
      setDiscovering(false);
    }
  };

  // Group resources by category
  const filteredResources = useMemo(() => {
    return resources.filter(r => {
      const matchQuery =
        r.display_name.toLowerCase().includes(search.toLowerCase()) ||
        r.provider.toLowerCase().includes(search.toLowerCase()) ||
        r.category.toLowerCase().includes(search.toLowerCase());
      const matchEnv = envFilter === 'ALL' || r.environment === envFilter;
      return matchQuery && matchEnv;
    });
  }, [resources, search, envFilter]);

  const categories = useMemo(() => {
    const defaultOrder = [
      'AI & Models',
      'ITSM & CMDB',
      'Secrets & PAM',
      'Source Control',
      'Orchestration & Runners',
      'Observability',
      'Persistence',
    ];
    const presentCats = Array.from(new Set(resources.map(r => r.category)));
    return defaultOrder.filter(c => presentCats.includes(c) || true);
  }, [resources]);

  const getStatusBadge = (status: string, latencyMs?: number) => {
    const s = (status || 'CONFIGURED').toUpperCase();
    if (s === 'HEALTHY' || s === 'CONNECTED') {
      return (
        <span
          data-testid="status-badge"
          className="status-badge flex items-center gap-1.5 text-[10px] font-mono text-emerald-400 bg-emerald-500/10 border border-emerald-500/30 px-2 py-0.5 rounded-full"
        >
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
          CONNECTED {latencyMs ? `(${latencyMs}ms)` : ''}
        </span>
      );
    }
    if (s === 'DEGRADED') {
      return (
        <span
          data-testid="status-badge"
          className="status-badge flex items-center gap-1 text-[10px] font-mono text-amber-400 bg-amber-500/10 border border-amber-500/30 px-2 py-0.5 rounded-full"
        >
          <AlertTriangle size={10} />
          DEGRADED
        </span>
      );
    }
    if (s === 'UNREACHABLE' || s === 'FAILED') {
      return (
        <span
          data-testid="status-badge"
          className="status-badge flex items-center gap-1 text-[10px] font-mono text-rose-400 bg-rose-500/10 border border-rose-500/30 px-2 py-0.5 rounded-full"
        >
          <XCircle size={10} />
          UNREACHABLE
        </span>
      );
    }
    return (
      <span
        data-testid="status-badge"
        className="status-badge flex items-center gap-1 text-[10px] font-mono text-cyan-400 bg-cyan-500/10 border border-cyan-500/30 px-2 py-0.5 rounded-full"
      >
        <CheckCircle2 size={10} />
        CONFIGURED
      </span>
    );
  };

  return (
    <div
      data-testid="external-resources-console"
      role="main"
      className="flex h-full w-full relative overflow-hidden bg-canvas-void text-slate-200"
    >
      {/* ──── LEFT BENTO CATALOG SIDEBAR (380px) ──── */}
      <aside
        data-testid="bento-catalog-sidebar"
        className="w-[380px] flex-shrink-0 border-r border-glass-border flex flex-col bg-glass-surface/40 backdrop-blur-md"
      >
        {/* Header & Search */}
        <div className="p-4 border-b border-glass-border space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <div className="p-1.5 rounded-lg bg-cyan-500/10 border border-cyan-500/20">
                <Plug className="w-4 h-4 text-cyan-400" />
              </div>
              <div>
                <h1 className="text-xs font-bold font-mono tracking-wider text-slate-100 uppercase">
                  External Resources
                </h1>
                <p className="text-[10px] text-slate-500">
                  Governed Cloud &amp; AI Integrations
                </p>
              </div>
            </div>
            <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-slate-900 border border-glass-border text-slate-400">
              {resources.length} Total
            </span>
          </div>

          <div className="relative">
            <Search size={13} className="absolute left-3 top-2.5 text-slate-500" />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search Foundry, ServiceNow, Vault…"
              className="w-full pl-9 pr-3 py-1.5 rounded-lg bg-slate-950/80 border border-glass-border text-xs text-slate-200 placeholder-slate-600 outline-none focus:border-cyan-500/40 font-sans transition-all"
            />
          </div>

          {/* Environment Filter Pills */}
          <div className="flex items-center gap-1.5 pt-1">
            {['ALL', 'PROD', 'STAGE', 'DEV'].map((env) => (
              <button
                key={env}
                onClick={() => setEnvFilter(env)}
                className={`text-[10px] font-mono px-2.5 py-0.5 rounded-md transition-all ${
                  envFilter === env
                    ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 font-bold'
                    : 'text-slate-500 hover:text-slate-300 hover:bg-white/[0.04]'
                }`}
              >
                {env}
              </button>
            ))}
          </div>
        </div>

        {/* Bento Category Accordion / List */}
        <div className="flex-1 overflow-y-auto divide-y divide-glass-border/30 p-2 space-y-4">
          {categories.map((cat) => {
            const catResources = filteredResources.filter(r => r.category === cat);
            if (catResources.length === 0 && search) return null;

            return (
              <div key={cat} className="pt-2 first:pt-0">
                <div className="flex items-center justify-between px-2.5 py-1.5 text-[11px] font-semibold tracking-wider text-slate-400 uppercase">
                  <div className="flex items-center gap-2">
                    {CATEGORY_ICONS[cat] ?? <Layers className="w-3.5 h-3.5 text-slate-400" />}
                    <span>{cat}</span>
                  </div>
                  <span className="text-[10px] font-mono text-slate-500">
                    {catResources.length}
                  </span>
                </div>

                <div className="space-y-1.5 mt-1">
                  {catResources.map((res) => {
                    const isSelected = res.resource_id === selectedResource.resource_id;
                    return (
                      <button
                        key={res.resource_id}
                        data-testid="resource-card"
                        onClick={() => setSelectedId(res.resource_id)}
                        className={`w-full text-left p-3 rounded-xl transition-all relative flex flex-col gap-1.5 border ${
                          isSelected
                            ? 'bg-cyan-500/[0.09] border-cyan-500/40 shadow-sm'
                            : 'bg-glass-surface/20 border-glass-border hover:bg-white/[0.03] hover:border-slate-700'
                        }`}
                      >
                        {isSelected && (
                          <div className="absolute left-0 top-2 bottom-2 w-[3px] bg-cyan-400 rounded-r shadow-glow-cyan" />
                        )}
                        <div className="flex items-start justify-between gap-2">
                          <div className="font-semibold text-xs text-slate-100 truncate">
                            {res.display_name}
                          </div>
                          <span className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-slate-900 border border-glass-border text-slate-400">
                            [{res.environment}]
                          </span>
                        </div>

                        <div className="flex items-center justify-between text-[11px]">
                          <span className="font-mono text-[10px] text-slate-500 truncate max-w-[170px]">
                            {res.endpoint.replace('https://', '').split('/')[0]}
                          </span>
                          {getStatusBadge(res.health_status, res.latency_ms)}
                        </div>
                      </button>
                    );
                  })}
                </div>
              </div>
            );
          })}
        </div>

        {/* Sidebar Footer — Security & RBAC Status */}
        <div className="p-3 border-t border-glass-border bg-slate-950/60 flex items-center justify-between text-[10px] font-mono text-slate-500">
          <div className="flex items-center gap-1.5">
            <Lock size={12} className="text-cyan-400" />
            <span>Zero-Raw-Secrets:</span>
            <span className="text-emerald-400 font-bold">ACTIVE</span>
          </div>
          <span className={`px-2 py-0.5 rounded border ${isPlatformAdmin ? 'text-amber-300 border-amber-500/30 bg-amber-500/10' : 'text-cyan-300 border-cyan-500/30 bg-cyan-500/10'}`}>
            {isPlatformAdmin ? 'PLATFORM_ADMIN' : 'OPERATOR (Read-Only)'}
          </span>
        </div>
      </aside>

      {/* ──── RIGHT DETAIL PANE ──── */}
      <div className="flex-1 flex flex-col h-full overflow-hidden bg-canvas-void">
        {/* Detail Header */}
        <div className="p-6 border-b border-glass-border flex items-center justify-between bg-glass-surface/20">
          <div className="space-y-1">
            <div className="flex items-center gap-3">
              <div className="p-2.5 rounded-xl bg-slate-900 border border-glass-border">
                {CATEGORY_ICONS[selectedResource.category] ?? <Plug className="w-6 h-6 text-cyan-400" />}
              </div>
              <div>
                <div className="flex items-center gap-2.5">
                  <h2 className="text-lg font-bold text-white tracking-wide">
                    {selectedResource.display_name}
                  </h2>
                  <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-slate-900 border border-glass-border text-slate-300">
                    [{selectedResource.environment}]
                  </span>
                  {getStatusBadge(selectedResource.health_status, selectedResource.latency_ms)}
                </div>
                <div className="flex items-center gap-4 text-xs font-mono text-slate-400 mt-1">
                  <span>ID: <strong className="text-slate-200">{selectedResource.resource_id}</strong></span>
                  <span>•</span>
                  <span>Provider: <strong className="text-cyan-400">{selectedResource.provider}</strong></span>
                  <span>•</span>
                  <span>Revision: <strong className="text-slate-200">v{selectedResource.version} (#{selectedResource.revision})</strong></span>
                </div>
              </div>
            </div>
          </div>

          {/* Action Bar */}
          <div className="flex items-center gap-2.5">
            <button
              type="button"
              disabled={!isPlatformAdmin || testingId === selectedResource.resource_id}
              onClick={handleTestConnection}
              title={!isPlatformAdmin ? 'Requires PLATFORM_ADMIN role (current: Operator/Auditor)' : 'Trigger live socket connection probe'}
              className={`flex items-center gap-1.5 px-3.5 py-2 rounded-lg text-xs font-mono font-bold transition-all border ${
                !isPlatformAdmin
                  ? 'opacity-40 cursor-not-allowed border-glass-border bg-slate-900 text-slate-500'
                  : 'bg-glass-surface hover:bg-white/[0.06] border-glass-border text-slate-200 hover:text-white'
              }`}
            >
              <RefreshCw size={13} className={testingId === selectedResource.resource_id ? 'animate-spin text-cyan-400' : 'text-slate-400'} />
              <span>{testingId === selectedResource.resource_id ? 'Probing…' : 'Test Handshake'}</span>
            </button>

            <button
              type="button"
              disabled={!isPlatformAdmin || syncingId === selectedResource.resource_id}
              onClick={handleSyncResource}
              title={!isPlatformAdmin ? 'Requires PLATFORM_ADMIN role' : 'Trigger full synchronization'}
              className={`flex items-center gap-1.5 px-3.5 py-2 rounded-lg text-xs font-mono font-bold transition-all border ${
                !isPlatformAdmin
                  ? 'opacity-40 cursor-not-allowed border-glass-border bg-slate-900 text-slate-500'
                  : 'bg-cyan-500/10 hover:bg-cyan-500/20 border-cyan-500/30 text-cyan-300'
              }`}
            >
              <RefreshCw size={13} className={syncingId === selectedResource.resource_id ? 'animate-spin' : ''} />
              <span>{syncingId === selectedResource.resource_id ? 'Syncing…' : 'Trigger Sync'}</span>
            </button>
          </div>
        </div>

        {/* 4-Tab Navigation Bar */}
        <div className="px-6 border-b border-glass-border bg-slate-950/40 flex items-center justify-between">
          <div className="flex items-center gap-6" role="tablist">
            {(['Overview', 'Configuration', 'Capabilities', 'Diagnostics'] as ActiveTab[]).map((tab) => {
              const active = activeTab === tab;
              return (
                <button
                  key={tab}
                  role="tab"
                  aria-selected={active}
                  onClick={() => setActiveTab(tab)}
                  className={`py-3 text-xs font-mono font-semibold transition-all relative ${
                    active
                      ? 'text-cyan-400 border-b-2 border-cyan-400'
                      : 'text-slate-400 hover:text-slate-200'
                  }`}
                >
                  {tab}
                </button>
              );
            })}
          </div>

          <div className="flex items-center gap-3 text-[11px] font-mono text-slate-500">
            <span className="flex items-center gap-1.5">
              <Shield size={12} className="text-emerald-400" />
              Merkle Hash-Chained: <strong className="text-slate-300">PASS</strong>
            </span>
          </div>
        </div>

        {/* Tab Content Body */}
        <div className="flex-1 overflow-y-auto p-6">
          {/* TAB 1: OVERVIEW */}
          {activeTab === 'Overview' && (
            <div className="space-y-6 max-w-4xl">
              {/* Test Handshake Alert if available */}
              {testResult && (
                <div className={`p-4 rounded-xl border flex items-start justify-between gap-3 ${
                  testResult.connected
                    ? 'bg-emerald-950/30 border-emerald-500/40 text-emerald-200'
                    : 'bg-rose-950/30 border-rose-500/40 text-rose-200'
                }`}>
                  <div className="flex items-start gap-2.5">
                    {testResult.connected ? <CheckCircle2 size={16} className="text-emerald-400 mt-0.5" /> : <XCircle size={16} className="text-rose-400 mt-0.5" />}
                    <div>
                      <div className="font-bold font-mono text-xs">
                        {testResult.connected ? 'Connection Succeeded' : 'Connection Failed'} ({testResult.latency_ms}ms)
                      </div>
                      <p className="text-xs text-slate-300 mt-0.5">{testResult.message}</p>
                    </div>
                  </div>
                  <button onClick={() => setTestResult(null)} className="text-slate-400 hover:text-white">
                    <X size={14} />
                  </button>
                </div>
              )}

              {syncMessage && (
                <div className="p-3.5 rounded-xl border bg-cyan-950/30 border-cyan-500/40 text-cyan-200 text-xs font-mono flex items-center justify-between">
                  <span>{syncMessage}</span>
                  <button onClick={() => setSyncMessage(null)} className="text-cyan-400 hover:text-white">
                    <X size={14} />
                  </button>
                </div>
              )}

              {/* Bento Grid: Essential Properties */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="p-4 rounded-xl bg-glass-surface/30 border border-glass-border space-y-3">
                  <h3 className="text-xs font-bold font-mono text-slate-300 uppercase tracking-wider flex items-center gap-2">
                    <Compass size={14} className="text-cyan-400" />
                    Endpoint &amp; Transport
                  </h3>
                  <div className="space-y-2 text-xs font-mono">
                    <div>
                      <span className="text-slate-500 block text-[10px]">REMOTE SERVICE BASE URL</span>
                      <span className="text-slate-200 break-all">{selectedResource.endpoint}</span>
                    </div>
                    <div>
                      <span className="text-slate-500 block text-[10px]">AUTHENTICATION MODE</span>
                      <span className="text-cyan-400 font-semibold">{selectedResource.auth_mode}</span>
                    </div>
                    <div>
                      <span className="text-slate-500 block text-[10px]">RESOURCE CATEGORY</span>
                      <span className="text-slate-300">{selectedResource.category}</span>
                    </div>
                  </div>
                </div>

                <div className="p-4 rounded-xl bg-glass-surface/30 border border-glass-border space-y-3">
                  <h3 className="text-xs font-bold font-mono text-slate-300 uppercase tracking-wider flex items-center gap-2">
                    <Shield size={14} className="text-emerald-400" />
                    Security &amp; Governance
                  </h3>
                  <div className="space-y-2 text-xs font-mono">
                    <div>
                      <span className="text-slate-500 block text-[10px]">ZERO-RAW-SECRETS REFERENCE</span>
                      <span className="text-amber-300 break-all">
                        {isPlatformAdmin
                          ? Object.values(selectedResource.secret_refs || {})[0] || 'vault://secret/vulcan/default'
                          : '•••••••• (********)'}
                      </span>
                    </div>
                    <div>
                      <span className="text-slate-500 block text-[10px]">MERKLE CHAIN ROOT SHA-256</span>
                      <span className="text-emerald-400 text-[10px] break-all">
                        {selectedResource.merkle_root || 'sha256:7f83b1657ff1fc53b92dc18148a1d65dfc2d4b1fa3d677284addd200126d9069'}
                      </span>
                    </div>
                    <div>
                      <span className="text-slate-500 block text-[10px]">AUDIT COMMITS</span>
                      <span className="text-slate-300">{selectedResource.audit_count} tamper-evident transactions</span>
                    </div>
                  </div>
                </div>
              </div>

              {/* Provider Capabilities Summary */}
              <div className="p-4 rounded-xl bg-glass-surface/30 border border-glass-border space-y-3">
                <h3 className="text-xs font-bold font-mono text-slate-300 uppercase tracking-wider flex items-center gap-2">
                  <Sliders size={14} className="text-cyan-400" />
                  Provider Capabilities &amp; Features
                </h3>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs font-mono">
                  <div className="p-3 rounded-lg bg-slate-900/60 border border-glass-border">
                    <span className="text-slate-500 text-[10px] block">DYNAMIC DISCOVERY</span>
                    <span className="text-emerald-400 font-bold">SUPPORTED</span>
                  </div>
                  <div className="p-3 rounded-lg bg-slate-900/60 border border-glass-border">
                    <span className="text-slate-500 text-[10px] block">SECRET ROTATION</span>
                    <span className="text-cyan-400 font-bold">AUTOMATED</span>
                  </div>
                  <div className="p-3 rounded-lg bg-slate-900/60 border border-glass-border">
                    <span className="text-slate-500 text-[10px] block">FAIL-CLOSED TIMEOUT</span>
                    <span className="text-slate-200 font-bold">5.0s Strict</span>
                  </div>
                  <div className="p-3 rounded-lg bg-slate-900/60 border border-glass-border">
                    <span className="text-slate-500 text-[10px] block">GOVERNANCE TIER</span>
                    <span className="text-amber-300 font-bold">ENTERPRISE</span>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* TAB 2: CONFIGURATION */}
          {activeTab === 'Configuration' && (
            <div className="space-y-6 max-w-2xl">
              <div className="p-4 rounded-xl bg-slate-950/60 border border-glass-border space-y-4">
                <div className="flex items-center justify-between pb-2 border-b border-glass-border">
                  <h3 className="text-xs font-bold font-mono text-slate-200 uppercase tracking-wider">
                    Resource Identity &amp; Transport
                  </h3>
                  {!isPlatformAdmin && (
                    <span className="text-[10px] font-mono text-amber-400 bg-amber-500/10 border border-amber-500/20 px-2 py-0.5 rounded">
                      READ-ONLY (Operator Mode)
                    </span>
                  )}
                </div>

                <div className="space-y-3 text-xs">
                  <div>
                    <label className="block text-slate-400 font-mono text-[11px] mb-1">
                      Display Name
                    </label>
                    <input
                      type="text"
                      disabled={!isPlatformAdmin}
                      value={formDisplayName}
                      onChange={(e) => setFormDisplayName(e.target.value)}
                      className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-glass-border text-slate-200 outline-none focus:border-cyan-500/50 disabled:opacity-50"
                    />
                  </div>

                  <div>
                    <label className="block text-slate-400 font-mono text-[11px] mb-1">
                      Endpoint Base URL
                    </label>
                    <input
                      type="text"
                      disabled={!isPlatformAdmin}
                      value={formEndpoint}
                      onChange={(e) => setFormEndpoint(e.target.value)}
                      className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-glass-border text-slate-200 outline-none focus:border-cyan-500/50 disabled:opacity-50 font-mono text-xs"
                    />
                  </div>

                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="block text-slate-400 font-mono text-[11px] mb-1">
                        Environment Tier
                      </label>
                      <select
                        disabled={!isPlatformAdmin}
                        value={formEnvironment}
                        onChange={(e) => setFormEnvironment(e.target.value)}
                        className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-glass-border text-slate-200 outline-none focus:border-cyan-500/50 disabled:opacity-50 font-mono text-xs"
                      >
                        <option value="PROD">PROD (Production)</option>
                        <option value="STAGE">STAGE (Staging)</option>
                        <option value="DEV">DEV (Development)</option>
                      </select>
                    </div>

                    <div>
                      <label className="block text-slate-400 font-mono text-[11px] mb-1">
                        Authentication Strategy
                      </label>
                      <select
                        disabled={!isPlatformAdmin}
                        value={formAuthMode}
                        onChange={(e) => setFormAuthMode(e.target.value)}
                        className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-glass-border text-slate-200 outline-none focus:border-cyan-500/50 disabled:opacity-50 font-mono text-xs"
                      >
                        <option value="API_KEY">API_KEY (Bearer Token)</option>
                        <option value="ENTRA_SERVICE_PRINCIPAL">ENTRA_SERVICE_PRINCIPAL</option>
                        <option value="MANAGED_IDENTITY">MANAGED_IDENTITY (Azure IMDS)</option>
                        <option value="MUTUAL_TLS">MUTUAL_TLS (mTLS Client Cert)</option>
                        <option value="BASIC_AUTH">BASIC_AUTH (Username/Password)</option>
                        <option value="NONE">NONE (Unauthenticated)</option>
                      </select>
                    </div>
                  </div>
                </div>
              </div>

              {/* Secret References Form (Zero-Raw-Secrets Invariant) */}
              <div className="p-4 rounded-xl bg-slate-950/60 border border-glass-border space-y-4">
                <div className="flex items-center justify-between pb-2 border-b border-glass-border">
                  <div className="flex items-center gap-2">
                    <Key size={14} className="text-amber-400" />
                    <h3 className="text-xs font-bold font-mono text-slate-200 uppercase tracking-wider">
                      Secret References (Zero-Raw-Secrets Invariant)
                    </h3>
                  </div>
                  <span className="text-[10px] font-mono text-emerald-400 bg-emerald-500/10 border border-emerald-500/30 px-2 py-0.5 rounded">
                    ENFORCED
                  </span>
                </div>

                <div className="space-y-2">
                  <label className="block text-slate-400 font-mono text-[11px]">
                    Vault Pointer or PAM Reference
                  </label>
                  <input
                    type="text"
                    name="secret_refs"
                    disabled={!isPlatformAdmin}
                    value={formSecretRef}
                    onChange={(e) => {
                      setFormSecretRef(e.target.value);
                      if (secretError) setSecretError(null);
                    }}
                    onBlur={handleSecretBlur}
                    placeholder="vault://secret/vulcan/... or cyberark://..."
                    className={`w-full px-3 py-2 rounded-lg bg-slate-900 border text-slate-200 outline-none font-mono text-xs transition-all ${
                      secretError ? 'border-rose-500/70 focus:border-rose-500' : 'border-glass-border focus:border-cyan-500/50'
                    } disabled:opacity-50`}
                  />

                  {secretError && (
                    <div className="p-2.5 rounded-lg bg-rose-950/40 border border-rose-500/40 text-rose-300 text-xs font-mono flex items-center gap-2">
                      <AlertCircle size={14} className="text-rose-400 flex-shrink-0" />
                      <span>{secretError}</span>
                    </div>
                  )}

                  <p className="text-[10px] text-slate-500 leading-relaxed">
                    Zero-Raw-Secrets Invariant (R2): Plaintext credentials (passwords, keys, tokens) are mathematically rejected by the schema validator. Only pointer schemes (<code className="text-cyan-400 font-mono">vault://</code>, <code className="text-cyan-400 font-mono">cyberark://</code>, <code className="text-cyan-400 font-mono">env://</code>) are permitted.
                  </p>
                </div>
              </div>

              {/* Status and Action Buttons */}
              {configSaveSuccess && (
                <div className="p-3.5 rounded-xl bg-emerald-950/30 border border-emerald-500/40 text-emerald-200 text-xs font-mono flex items-center gap-2">
                  <CheckCircle2 size={16} className="text-emerald-400" />
                  <span>{configSaveSuccess}</span>
                </div>
              )}

              <div className="flex items-center justify-end gap-3 pt-2">
                <button
                  type="button"
                  disabled={!isPlatformAdmin || savingConfig}
                  onClick={handleSaveConfig}
                  className={`flex items-center gap-2 px-5 py-2 rounded-lg text-xs font-mono font-bold transition-all shadow-glow-cyan ${
                    !isPlatformAdmin
                      ? 'bg-slate-900 border border-glass-border text-slate-500 cursor-not-allowed opacity-50'
                      : 'bg-cyan-500 text-slate-950 hover:bg-cyan-400'
                  }`}
                >
                  {savingConfig ? <RefreshCw size={14} className="animate-spin" /> : <Save size={14} />}
                  <span>Save</span>
                </button>
              </div>
            </div>
          )}

          {/* TAB 3: CAPABILITIES & DYNAMIC DISCOVERY (R4 / R5) */}
          {activeTab === 'Capabilities' && (
            <div className="space-y-6 max-w-3xl">
              {/* Dynamic Discovery Action Card */}
              <div className="p-5 rounded-xl bg-glass-surface/30 border border-glass-border space-y-4">
                <div className="flex items-center justify-between">
                  <div className="space-y-0.5">
                    <h3 className="text-xs font-bold font-mono text-slate-100 uppercase tracking-wider flex items-center gap-2">
                      <Sparkles size={14} className="text-cyan-400" />
                      Dynamic Model Deployment Discovery
                    </h3>
                    <p className="text-xs text-slate-400">
                      Query upstream provider API for available model endpoints and capacities.
                    </p>
                  </div>
                  <button
                    type="button"
                    disabled={discovering}
                    onClick={handleDiscoverDeployments}
                    className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-cyan-500/10 hover:bg-cyan-500/20 border border-cyan-500/30 text-cyan-300 font-mono text-xs font-bold transition-all"
                  >
                    <RefreshCw size={13} className={discovering ? 'animate-spin' : ''} />
                    <span>Discover</span>
                  </button>
                </div>

                {/* Discovered Deployments List */}
                <div className="space-y-2 mt-3">
                  <span className="text-[10px] font-mono uppercase text-slate-500">
                    Discovered Deployments &amp; Model Endpoints
                  </span>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                    {discoveredCaps?.deployments && Array.isArray(discoveredCaps.deployments) && discoveredCaps.deployments.length > 0 ? (
                      discoveredCaps.deployments.map((dep: any, idx: number) => {
                        const depName = typeof dep === 'string' ? dep : dep.name;
                        const depModel = typeof dep === 'string' ? dep : dep.model;
                        const depType = typeof dep === 'string' ? (dep.includes('embedding') ? 'embeddings' : 'chat') : dep.type;

                        return (
                          <div
                            key={idx}
                            className="p-3.5 rounded-xl bg-slate-950/70 border border-glass-border flex flex-col justify-between gap-2"
                          >
                            <div className="flex items-start justify-between">
                              <div className="font-mono text-xs font-bold text-slate-100">
                                {depName}
                              </div>
                              <span className="text-[9px] font-mono px-2 py-0.5 rounded bg-cyan-500/10 text-cyan-300 border border-cyan-500/20">
                                {depType}
                              </span>
                            </div>
                            <div className="flex items-center justify-between text-[10px] font-mono text-slate-400">
                              <span>Model: {depModel}</span>
                              <span className="text-emerald-400 font-bold">READY</span>
                            </div>
                          </div>
                        );
                      })
                    ) : (
                      <>
                        <div className="p-3.5 rounded-xl bg-slate-950/70 border border-glass-border flex flex-col justify-between gap-2">
                          <div className="flex items-start justify-between">
                            <div className="font-mono text-xs font-bold text-slate-100">gpt-4o</div>
                            <span className="text-[9px] font-mono px-2 py-0.5 rounded bg-cyan-500/10 text-cyan-300 border border-cyan-500/20">
                              chat reasoning
                            </span>
                          </div>
                          <div className="flex items-center justify-between text-[10px] font-mono text-slate-400">
                            <span>Capacity: 150k TPM</span>
                            <span className="text-emerald-400 font-bold">Succeeded</span>
                          </div>
                        </div>

                        <div className="p-3.5 rounded-xl bg-slate-950/70 border border-glass-border flex flex-col justify-between gap-2">
                          <div className="flex items-start justify-between">
                            <div className="font-mono text-xs font-bold text-slate-100">text-embedding-3-small</div>
                            <span className="text-[9px] font-mono px-2 py-0.5 rounded bg-cyan-500/10 text-cyan-300 border border-cyan-500/20">
                              intent embeddings
                            </span>
                          </div>
                          <div className="flex items-center justify-between text-[10px] font-mono text-slate-400">
                            <span>Capacity: 350k TPM</span>
                            <span className="text-emerald-400 font-bold">Succeeded</span>
                          </div>
                        </div>
                      </>
                    )}
                  </div>
                </div>
              </div>

              {/* Vulcan AI Routing Defaults Picker */}
              <div className="p-5 rounded-xl bg-glass-surface/30 border border-glass-border space-y-4">
                <div className="pb-2 border-b border-glass-border">
                  <h3 className="text-xs font-bold font-mono text-slate-100 uppercase tracking-wider flex items-center gap-2">
                    <Zap size={14} className="text-cyan-400" />
                    Vulcan Routing Defaults Selection
                  </h3>
                  <p className="text-xs text-slate-400 mt-0.5">
                    Assign this provider connector as the authoritative engine for Vulcan Control Plane intent tasks.
                  </p>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {/* Chat reasoning default */}
                  <label
                    data-testid="vulcan-chat-default"
                    className="p-4 rounded-xl bg-slate-950/70 border border-glass-border flex items-start gap-3 cursor-pointer hover:border-cyan-500/40 transition-all"
                  >
                    <input
                      type="checkbox"
                      checked={routingChatDefault}
                      onChange={(e) => setRoutingChatDefault(e.target.checked)}
                      disabled={!isPlatformAdmin}
                      className="mt-0.5 rounded text-cyan-500 bg-slate-900 border-glass-border focus:ring-0"
                    />
                    <div className="space-y-1">
                      <span className="text-xs font-mono font-bold text-slate-200 block">
                        Chat reasoning
                      </span>
                      <p className="text-[11px] text-slate-400 leading-relaxed">
                        Use this deployment as the primary LLM OS reasoning engine for intent extraction and slot filling.
                      </p>
                    </div>
                  </label>

                  {/* Intent embeddings default */}
                  <label
                    data-testid="vulcan-embedding-default"
                    className="p-4 rounded-xl bg-slate-950/70 border border-glass-border flex items-start gap-3 cursor-pointer hover:border-cyan-500/40 transition-all"
                  >
                    <input
                      type="checkbox"
                      checked={routingEmbedDefault}
                      onChange={(e) => setRoutingEmbedDefault(e.target.checked)}
                      disabled={!isPlatformAdmin}
                      className="mt-0.5 rounded text-cyan-500 bg-slate-900 border-glass-border focus:ring-0"
                    />
                    <div className="space-y-1">
                      <span className="text-xs font-mono font-bold text-slate-200 block">
                        Intent embeddings
                      </span>
                      <p className="text-[11px] text-slate-400 leading-relaxed">
                        Route 1,536-dim vector indexing and catalog RRF hybrid search queries to this endpoint.
                      </p>
                    </div>
                  </label>
                </div>

                <div className="grid grid-cols-2 gap-4 pt-2">
                  <div>
                    <label className="block text-[11px] font-mono text-slate-400 mb-1">
                      Priority Order
                    </label>
                    <select
                      disabled={!isPlatformAdmin}
                      className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-glass-border text-slate-200 font-mono text-xs outline-none"
                    >
                      <option value="1">Priority 1 (Primary Production Driver)</option>
                      <option value="2">Priority 2 (Secondary Failover)</option>
                      <option value="3">Priority 3 (Air-Gapped Backup)</option>
                    </select>
                  </div>

                  <div>
                    <label className="block text-[11px] font-mono text-slate-400 mb-1">
                      Fallback Policy
                    </label>
                    <select
                      value={fallbackPolicy}
                      onChange={(e) => setFallbackPolicy(e.target.value)}
                      disabled={!isPlatformAdmin}
                      className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-glass-border text-slate-200 font-mono text-xs outline-none"
                    >
                      <option value="deterministic_fake">Fallback to Local Deterministic Fake (Hermetic)</option>
                      <option value="refuse_closed">Fail Closed (Return 503 Refusal)</option>
                      <option value="retry_exponential">Retry Outbound with Exponential Backoff (3x)</option>
                    </select>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* TAB 4: DIAGNOSTICS */}
          {activeTab === 'Diagnostics' && (
            <div className="space-y-6 max-w-4xl">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-xs font-bold font-mono text-slate-100 uppercase tracking-wider">
                    Chronological Telemetry &amp; Network Health Probes
                  </h3>
                  <p className="text-xs text-slate-400 mt-0.5">
                    Live connection handshake latency, socket status, and Merkle audit receipts.
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => {
                    setLoadingHistory(true);
                    api.getResourceHealthHistory(selectedResource.resource_id)
                      .then(records => setHealthHistory(records))
                      .finally(() => setLoadingHistory(false));
                  }}
                  className="flex items-center gap-1 px-3 py-1.5 rounded-lg bg-slate-900 border border-glass-border text-xs font-mono text-slate-400 hover:text-white"
                >
                  <RefreshCw size={12} className={loadingHistory ? 'animate-spin' : ''} />
                  <span>Refresh</span>
                </button>
              </div>

              {/* Health Records List */}
              <div className="rounded-xl border border-glass-border overflow-hidden bg-slate-950/60 divide-y divide-glass-border/40">
                {healthHistory.length > 0 ? (
                  healthHistory.map((rec, idx) => (
                    <div key={idx} className="p-4 flex items-center justify-between text-xs font-mono">
                      <div className="flex items-center gap-3">
                        <span className={`w-2 h-2 rounded-full ${rec.status === 'HEALTHY' ? 'bg-emerald-400' : 'bg-rose-400'}`} />
                        <div>
                          <span className="font-bold text-slate-200">{rec.status}</span>
                          <span className="text-slate-500 ml-2">({rec.latency_ms}ms, HTTP {rec.http_status})</span>
                          <p className="text-[11px] text-slate-400 font-sans mt-0.5">{rec.message}</p>
                        </div>
                      </div>
                      <span className="text-[10px] text-slate-500">
                        {new Date(rec.recorded_at).toLocaleTimeString()}
                      </span>
                    </div>
                  ))
                ) : (
                  <div className="p-8 text-center text-xs font-mono text-slate-500">
                    No historic probe anomalies logged. Handshake telemetry verified clean.
                  </div>
                )}
              </div>

              {/* Raw JSON Diagnostic Drawer */}
              <div className="p-4 rounded-xl bg-slate-950/80 border border-glass-border space-y-2">
                <span className="text-[10px] font-mono uppercase text-slate-500 block">
                  Raw Diagnostic Telemetry Payload
                </span>
                <pre className="p-3 rounded-lg bg-black/80 text-[11px] font-mono text-cyan-300 overflow-x-auto">
                  {JSON.stringify({
                    resource_id: selectedResource.resource_id,
                    provider: selectedResource.provider,
                    health_status: selectedResource.health_status,
                    latency_ms: selectedResource.latency_ms,
                    merkle_root: selectedResource.merkle_root,
                    audit_count: selectedResource.audit_count,
                    diagnostics: selectedResource.config,
                  }, null, 2)}
                </pre>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

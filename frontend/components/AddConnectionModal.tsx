'use client';

import React, { useState } from 'react';
import {
  Plug,
  Server,
  Database,
  Cloud,
  Shield,
  Activity,
  Box,
  CheckCircle2,
  AlertCircle,
  RefreshCw,
  X,
  ArrowRight,
  ArrowLeft,
  Lock,
  Layers,
  Sparkles,
} from 'lucide-react';
import { getApiBaseUrl } from '@/lib/env';

export interface ProviderDefinition {
  id: string;
  name: string;
  category: string;
  icon: React.ReactNode;
  description: string;
  capabilityEnabled: string;
  defaultEndpoint: string;
  authModes: string[];
  defaultConfig: Record<string, any>;
  defaultSecrets: Record<string, string>;
}

const PROVIDERS: ProviderDefinition[] = [
  {
    id: 'docker',
    name: 'Docker Daemon',
    category: 'CONTAINER_PLATFORM',
    icon: <Box className="w-5 h-5 text-sky-400" />,
    description: 'Local or remote Docker engine for containerized infrastructure.',
    capabilityEnabled: 'Enables deploying, running, and inspecting containerized services and executing socket health probes.',
    defaultEndpoint: 'unix:///var/run/docker.sock',
    authModes: ['NONE', 'MUTUAL_TLS'],
    defaultConfig: { socket_path: '/var/run/docker.sock' },
    defaultSecrets: {},
  },
  {
    id: 'ansible_ssh',
    name: 'Linux SSH Target',
    category: 'CLOUD_INFRASTRUCTURE',
    icon: <Server className="w-5 h-5 text-emerald-400" />,
    description: 'Target Linux host or cluster for playbook configuration and software provisioning.',
    capabilityEnabled: 'Enables OS package installation (Redis, PostgreSQL, Nginx), systemd service management, and dynamic port probing.',
    defaultEndpoint: 'ssh://dev-cache-01.internal:22',
    authModes: ['API_KEY', 'MUTUAL_TLS', 'BASIC'],
    defaultConfig: { username: 'ansible_svc', sudo: true },
    defaultSecrets: { ssh_private_key: 'vault://secret/vulcan/ssh_key' },
  },
  {
    id: 'galaxy',
    name: 'Ansible Galaxy',
    category: 'REGISTRY',
    icon: <Layers className="w-5 h-5 text-cyan-400" />,
    description: 'Ansible Galaxy or enterprise private automation registry.',
    capabilityEnabled: 'Enables discovering, downloading, and caching cryptographically verified community and vendor roles.',
    defaultEndpoint: 'https://galaxy.ansible.com',
    authModes: ['NONE', 'BEARER_TOKEN'],
    defaultConfig: { server_url: 'https://galaxy.ansible.com' },
    defaultSecrets: {},
  },
  {
    id: 's3',
    name: 'AWS S3 / MinIO',
    category: 'STORAGE_DATA',
    icon: <Database className="w-5 h-5 text-amber-400" />,
    description: 'Object storage for automated pre-change snapshots and backup verification.',
    capabilityEnabled: 'Enables policy-mandated backup snapshots before applying mutations, and verifies backup restoration accessibility.',
    defaultEndpoint: 'https://s3.amazonaws.com',
    authModes: ['API_KEY', 'AWS_IAM'],
    defaultConfig: { bucket: 'vulcan-backups', region: 'us-east-1' },
    defaultSecrets: { role_arn: 'vault://secret/vulcan/s3_backup_role' },
  },
  {
    id: 'datadog',
    name: 'Datadog APM',
    category: 'MONITORING_TELEMETRY',
    icon: <Activity className="w-5 h-5 text-purple-400" />,
    description: 'Datadog telemetry and APM monitoring integration.',
    capabilityEnabled: 'Enables evaluating organizational telemetry policies and live host metrics verification.',
    defaultEndpoint: 'https://api.datadoghq.com',
    authModes: ['API_KEY'],
    defaultConfig: { site: 'datadoghq.com' },
    defaultSecrets: { api_key: 'vault://secret/vulcan/datadog_key' },
  },
  {
    id: 'cyberark',
    name: 'CyberArk CCP',
    category: 'SECRETS_PAM',
    icon: <Shield className="w-5 h-5 text-rose-400" />,
    description: 'CyberArk Central Credential Provider for zero-raw-secret credential retrieval.',
    capabilityEnabled: 'Enables dynamic zero-raw-secrets credential injection using safe pointer references.',
    defaultEndpoint: 'https://cyberark.internal.net/AIMWebService',
    authModes: ['MUTUAL_TLS'],
    defaultConfig: { app_id: 'VULCAN_CONTROL_PLANE' },
    defaultSecrets: { client_cert: 'cyberark://vulcan/pki/cert' },
  },
  {
    id: 'servicenow',
    name: 'ServiceNow ITSM',
    category: 'ITSM_CMDB',
    icon: <Cloud className="w-5 h-5 text-indigo-400" />,
    description: 'ServiceNow Change Management and CMDB integration.',
    capabilityEnabled: 'Enables automated change ticket verification, change window enforcement, and CMDB CI updates.',
    defaultEndpoint: 'https://enterprise.service-now.com',
    authModes: ['BASIC', 'BEARER_TOKEN'],
    defaultConfig: { username: 'vulcan_service_acct' },
    defaultSecrets: { password: 'vault://secret/vulcan/servicenow/password' },
  },
];

export interface AddConnectionModalProps {
  isOpen: boolean;
  onClose: () => void;
  onCreated?: (newResource: any) => void;
  onSaved?: (newResource: any) => void;
  initialProvider?: string;
  workflowIdToResume?: string | null;
  returnTo?: string;
}

export function AddConnectionModal({
  isOpen,
  onClose,
  onCreated,
  onSaved,
  initialProvider,
  workflowIdToResume,
  returnTo,
}: AddConnectionModalProps) {
  const [step, setStep] = useState<1 | 2 | 3>(1);
  const [selectedProvider, setSelectedProvider] = useState<ProviderDefinition>(() => {
    return PROVIDERS.find((p) => p.id === initialProvider) ?? PROVIDERS[0];
  });

  // Form states
  const [displayName, setDisplayName] = useState('');
  const [environment, setEnvironment] = useState<'DEV' | 'STAGE' | 'PROD'>('DEV');
  const [endpoint, setEndpoint] = useState('');
  const [authMode, setAuthMode] = useState('NONE');
  const [secretPointer, setSecretPointer] = useState('');

  // Probe testing states
  const [isTesting, setIsTesting] = useState(false);
  const [testResult, setTestResult] = useState<any | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleSelectProvider = (prov: ProviderDefinition) => {
    setSelectedProvider(prov);
    setDisplayName(`${prov.name} (${environment})`);
    setEndpoint(prov.defaultEndpoint);
    setAuthMode(prov.authModes[0]);
    const firstSecret = Object.values(prov.defaultSecrets)[0] || '';
    setSecretPointer(firstSecret);
    setTestResult(null);
    setErrorMessage(null);
    setStep(2);
  };

  const handleRunTestProbe = async () => {
    setIsTesting(true);
    setTestResult(null);
    setErrorMessage(null);

    const baseUrl = getApiBaseUrl();
    const token = typeof window !== 'undefined' ? window.localStorage.getItem('vulcan_api_token') : null;

    try {
      const res = await fetch(`${baseUrl}/api/v1/external-resources/test-connection`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({
          provider: selectedProvider.id,
          endpoint: endpoint.trim() || selectedProvider.defaultEndpoint,
          config: selectedProvider.defaultConfig,
          secret_refs: secretPointer ? { primary: secretPointer.trim() } : {},
        }),
      });

      const data = await res.json();
      if (res.ok) {
        setTestResult(data);
      } else {
        setErrorMessage(data.message || data.detail || 'Connection test failed');
        setTestResult({ status: 'FAILED', message: data.detail || 'Probe unreachable' });
      }
    } catch (e: any) {
      setErrorMessage(e.message || 'Network probe failed');
      setTestResult({ status: 'FAILED', message: e.message });
    } finally {
      setIsTesting(false);
    }
  };

  const handleSaveConnection = async () => {
    setIsSaving(true);
    setErrorMessage(null);

    const baseUrl = getApiBaseUrl();
    const token = typeof window !== 'undefined' ? window.localStorage.getItem('vulcan_api_token') : null;
    const resourceId = `res-${selectedProvider.id}-${Date.now().toString(36)}`;

    try {
      const res = await fetch(`${baseUrl}/api/v1/external-resources`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({
          resource_id: resourceId,
          provider: selectedProvider.id,
          category: selectedProvider.category,
          display_name: displayName.trim() || selectedProvider.name,
          environment: environment,
          endpoint: endpoint.trim() || selectedProvider.defaultEndpoint,
          auth_mode: authMode,
          enabled: true,
          config: selectedProvider.defaultConfig,
          secret_refs: secretPointer ? { primary: secretPointer.trim() } : {},
        }),
      });

      if (res.ok) {
        const created = await res.json();
        if (onCreated) onCreated(created);
        if (onSaved) onSaved(created);

        // If a workflow was halted waiting for this resource, resume it automatically!
        if (workflowIdToResume) {
          await fetch(`${baseUrl}/api/v1/agentos/workflows/${encodeURIComponent(workflowIdToResume)}/resume`, {
            method: 'POST',
            headers: { ...(token ? { Authorization: `Bearer ${token}` } : {}) },
          }).catch(() => {});
        }

        onClose();
      } else {
        const err = await res.json().catch(() => ({}));
        setErrorMessage(err.message || err.detail || 'Failed to save connection');
      }
    } catch (e: any) {
      setErrorMessage(e.message || 'Error saving connection');
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-md animate-fade-in">
      <div className="w-full max-w-2xl bg-slate-900 border border-glass-border rounded-2xl shadow-2xl overflow-hidden flex flex-col max-h-[90vh]">
        {/* Header */}
        <div className="px-6 py-4 border-b border-glass-border flex items-center justify-between bg-slate-950/50">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-cyan-500/10 border border-cyan-500/30 text-cyan-400">
              <Plug size={18} />
            </div>
            <div>
              <h2 className="text-sm font-bold text-white tracking-wide">
                {step === 1 ? 'Add External Connection — Choose Provider' : `Configure ${selectedProvider.name}`}
              </h2>
              <p className="text-[11px] text-slate-400 font-mono">
                {step === 1 ? 'Select the infrastructure or service to connect' : 'Define credentials and test live reachability'}
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
          >
            <X size={16} />
          </button>
        </div>

        {/* Step Indicator */}
        <div className="px-6 py-2.5 bg-slate-950/30 border-b border-glass-border flex items-center justify-between text-xs font-mono">
          <div className="flex items-center gap-2">
            <span className={`w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-bold ${
              step >= 1 ? 'bg-cyan-500 text-slate-950' : 'bg-slate-800 text-slate-400'
            }`}>1</span>
            <span className={step >= 1 ? 'text-slate-200' : 'text-slate-500'}>Choose Provider</span>
          </div>
          <div className="w-8 h-px bg-slate-800" />
          <div className="flex items-center gap-2">
            <span className={`w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-bold ${
              step >= 2 ? 'bg-cyan-500 text-slate-950' : 'bg-slate-800 text-slate-400'
            }`}>2</span>
            <span className={step >= 2 ? 'text-slate-200' : 'text-slate-500'}>Configure &amp; Test</span>
          </div>
        </div>

        {/* Modal Body */}
        <div className="p-6 flex-1 overflow-y-auto space-y-5">
          {errorMessage && (
            <div className="p-3 rounded-lg bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs font-mono flex items-start gap-2">
              <AlertCircle size={14} className="flex-shrink-0 mt-0.5 text-rose-400" />
              <span>{errorMessage}</span>
            </div>
          )}

          {/* STEP 1: CHOOSE PROVIDER */}
          {step === 1 && (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {PROVIDERS.map((prov) => (
                <div
                  key={prov.id}
                  onClick={() => handleSelectProvider(prov)}
                  className="p-4 rounded-xl bg-slate-950/60 border border-glass-border hover:border-cyan-500/50 hover:bg-slate-800/60 transition-all cursor-pointer group flex flex-col justify-between"
                >
                  <div>
                    <div className="flex items-center justify-between mb-2">
                      <div className="p-2 rounded-lg bg-slate-900 border border-glass-border group-hover:border-cyan-500/30">
                        {prov.icon}
                      </div>
                      <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-slate-900 border border-slate-800 text-slate-400">
                        {prov.category}
                      </span>
                    </div>
                    <h3 className="text-xs font-bold text-white group-hover:text-cyan-300 transition-colors mb-1 font-mono">
                      {prov.name}
                    </h3>
                    <p className="text-[11px] text-slate-400 line-clamp-2 leading-relaxed font-sans mb-3">
                      {prov.description}
                    </p>
                  </div>
                  <div className="pt-2 border-t border-glass-border/40 text-[10px] text-slate-500 font-mono flex items-center justify-between">
                    <span>Default: {prov.defaultEndpoint.slice(0, 24)}…</span>
                    <ArrowRight size={12} className="text-cyan-400 opacity-0 group-hover:opacity-100 transition-opacity" />
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* STEP 2: CONFIGURE & TEST */}
          {step === 2 && (
            <div className="space-y-4">
              {/* Capability Enabled Banner */}
              <div className="p-3.5 rounded-xl bg-cyan-950/40 border border-cyan-500/30 text-xs flex items-start gap-3">
                <Sparkles size={16} className="text-cyan-400 flex-shrink-0 mt-0.5" />
                <div>
                  <span className="font-mono font-bold text-cyan-300 block mb-0.5 uppercase tracking-wide text-[10px]">
                    Capabilities Granted to Vulcan
                  </span>
                  <p className="text-slate-300 leading-relaxed font-sans text-xs">
                    {selectedProvider.capabilityEnabled}
                  </p>
                </div>
              </div>

              {/* Configuration Form */}
              <div className="space-y-3 font-mono text-xs">
                <div>
                  <label className="block text-slate-400 mb-1 font-semibold">Display Name</label>
                  <input
                    type="text"
                    value={displayName}
                    onChange={(e) => setDisplayName(e.target.value)}
                    placeholder={selectedProvider.name}
                    className="w-full bg-slate-950 border border-glass-border rounded-lg px-3 py-2 text-white placeholder-slate-600 focus:outline-none focus:border-cyan-400"
                  />
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-slate-400 mb-1 font-semibold">Environment</label>
                    <select
                      value={environment}
                      onChange={(e) => setEnvironment(e.target.value as any)}
                      className="w-full bg-slate-950 border border-glass-border rounded-lg px-3 py-2 text-white focus:outline-none focus:border-cyan-400"
                    >
                      <option value="DEV">DEV (Non-Production)</option>
                      <option value="STAGE">STAGE (Pre-Production)</option>
                      <option value="PROD">PROD (Production)</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-slate-400 mb-1 font-semibold">Authentication Mode</label>
                    <select
                      value={authMode}
                      onChange={(e) => setAuthMode(e.target.value)}
                      className="w-full bg-slate-950 border border-glass-border rounded-lg px-3 py-2 text-white focus:outline-none focus:border-cyan-400"
                    >
                      {selectedProvider.authModes.map((m) => (
                        <option key={m} value={m}>{m}</option>
                      ))}
                    </select>
                  </div>
                </div>

                <div>
                  <label className="block text-slate-400 mb-1 font-semibold">Endpoint URL / Socket URI</label>
                  <input
                    type="text"
                    value={endpoint}
                    onChange={(e) => setEndpoint(e.target.value)}
                    placeholder={selectedProvider.defaultEndpoint}
                    className="w-full bg-slate-950 border border-glass-border rounded-lg px-3 py-2 text-white placeholder-slate-600 focus:outline-none focus:border-cyan-400"
                  />
                </div>

                <div>
                  <label className="block text-slate-400 mb-1 font-semibold flex items-center justify-between">
                    <span>Secret Pointer Reference (Zero-Raw-Secrets)</span>
                    <span className="text-[10px] text-slate-500 font-sans">vault://, env://, or cyberark://</span>
                  </label>
                  <input
                    type="text"
                    value={secretPointer}
                    onChange={(e) => setSecretPointer(e.target.value)}
                    placeholder="vault://secret/vulcan/provider_key"
                    className="w-full bg-slate-950 border border-glass-border rounded-lg px-3 py-2 text-white placeholder-slate-600 focus:outline-none focus:border-cyan-400"
                  />
                </div>
              </div>

              {/* Probe Test Action & Result */}
              <div className="pt-2 border-t border-glass-border">
                <div className="flex items-center justify-between">
                  <button
                    type="button"
                    onClick={handleRunTestProbe}
                    disabled={isTesting}
                    className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 border border-cyan-500/30 text-cyan-300 font-mono text-xs flex items-center gap-2 transition-all cursor-pointer"
                  >
                    {isTesting ? <RefreshCw size={12} className="animate-spin text-cyan-400" /> : <Activity size={12} className="text-cyan-400" />}
                    <span>Test Connection Probe</span>
                  </button>

                  {testResult && (
                    <div className="flex items-center gap-2 text-xs font-mono">
                      {testResult.status === 'HEALTHY' || testResult.status === 'CONFIGURED' ? (
                        <span className="flex items-center gap-1.5 text-emerald-400">
                          <CheckCircle2 size={14} />
                          <span>Reachable ({testResult.latency_ms ?? 14}ms)</span>
                        </span>
                      ) : (
                        <span className="flex items-center gap-1.5 text-rose-400">
                          <AlertCircle size={14} />
                          <span>Probe Failed</span>
                        </span>
                      )}
                    </div>
                  )}
                </div>

                {testResult && testResult.message && (
                  <p className="mt-2 text-[11px] font-mono text-slate-400 bg-slate-950/60 p-2 rounded border border-glass-border">
                    {testResult.message}
                  </p>
                )}
              </div>
            </div>
          )}
        </div>

        {/* Modal Footer */}
        <div className="px-6 py-4 border-t border-glass-border bg-slate-950/50 flex items-center justify-between font-mono text-xs">
          {step === 2 ? (
            <button
              type="button"
              onClick={() => setStep(1)}
              className="px-3 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 flex items-center gap-1.5 transition-colors cursor-pointer"
            >
              <ArrowLeft size={13} />
              <span>Back to Providers</span>
            </button>
          ) : (
            <div />
          )}

          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={onClose}
              className="px-3 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-400 hover:text-white transition-colors cursor-pointer"
            >
              Cancel
            </button>

            {step === 2 && (
              <button
                type="button"
                onClick={handleSaveConnection}
                disabled={isSaving}
                className="px-4 py-2 rounded-lg bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-bold flex items-center gap-1.5 transition-all shadow-glow-cyan cursor-pointer disabled:opacity-40"
              >
                {isSaving ? <RefreshCw size={13} className="animate-spin" /> : <CheckCircle2 size={14} />}
                <span>Save Connection</span>
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

export default AddConnectionModal;

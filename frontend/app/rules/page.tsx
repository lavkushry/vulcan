'use client';

import React, { useState, useMemo } from 'react';
import {
  GitBranch, Search, Zap, CheckCircle2, XCircle, Play,
  AlertTriangle, Shield, Clock, Plus, ToggleLeft, ToggleRight,
  ArrowRight, Radio, Filter, Cpu, Database, Bell, Terminal
} from 'lucide-react';
import { AppShell } from '@/components/layout/AppShell';

interface AutomationRule {
  id: string;
  name: string;
  description: string;
  enabled: boolean;
  trigger: {
    type: 'datadog_alert' | 'servicenow_incident' | 'prometheus_alert' | 'schedule_cron' | 'kafka_event';
    source: string;
    event_name: string;
    criteria: { field: string; operator: string; value: string }[];
  };
  action: {
    identifier: string;
    name: string;
    engine: 'ansible' | 'terraform';
    parameter_mappings: Record<string, string>;
  };
  governance: {
    requires_lead_approval: boolean;
    auto_create_chg: boolean;
    cooldown_seconds: number;
  };
  stats: {
    total_triggered: number;
    last_triggered_at: string | null;
    success_rate: number;
  };
}

const PRESET_RULES: AutomationRule[] = [
  {
    id: 'rule-cert-renewal',
    name: 'Auto-Renew Expiring SSL Certs (F5 BIG-IP)',
    description: 'Triggered when Datadog TLS monitor warns of SSL expiry within 30 days. Dispatches F5 ACME certificate renewal.',
    enabled: true,
    trigger: {
      type: 'datadog_alert',
      source: 'datadog-monitors-us-east',
      event_name: 'tls.certificate.expiration_warning',
      criteria: [
        { field: 'days_until_expiry', operator: '<=', value: '30' },
        { field: 'environment', operator: '==', value: 'PROD' }
      ]
    },
    action: {
      identifier: 'net-f5-cert-renew',
      name: 'F5 BIG-IP SSL Certificate Renewal',
      engine: 'ansible',
      parameter_mappings: {
        hostname: '{{ trigger.payload.vip_hostname }}',
        vip_ip: '{{ trigger.payload.vip_ip }}',
        cert_valid_days: '90',
        environment: '{{ trigger.payload.environment }}',
        servicenow_chg: '{{ trigger.payload.auto_chg_ticket }}'
      }
    },
    governance: {
      requires_lead_approval: true,
      auto_create_chg: true,
      cooldown_seconds: 3600
    },
    stats: {
      total_triggered: 42,
      last_triggered_at: '2026-09-05T18:32:10Z',
      success_rate: 97.6
    }
  },
  {
    id: 'rule-tablespace-expand',
    name: 'Auto-Remediate DB Tablespace Full Alert',
    description: 'Triggered by Oracle/Postgres high storage alert (>85%). Expands tablespace by 50GB on target cluster.',
    enabled: true,
    trigger: {
      type: 'prometheus_alert',
      source: 'k8s-prometheus-prod',
      event_name: 'DatabaseStorageFullCritical',
      criteria: [
        { field: 'used_percent', operator: '>=', value: '85' },
        { field: 'tier', operator: '==', value: 'tier-1-banking' }
      ]
    },
    action: {
      identifier: 'db-oracle-tablespace-expand',
      name: 'Oracle Tablespace Storage Expansion',
      engine: 'ansible',
      parameter_mappings: {
        cluster_id: '{{ trigger.payload.cluster }}',
        increment_gb: '50',
        auto_extend: 'true',
        environment: 'PROD'
      }
    },
    governance: {
      requires_lead_approval: true,
      auto_create_chg: true,
      cooldown_seconds: 1800
    },
    stats: {
      total_triggered: 19,
      last_triggered_at: '2026-09-04T09:14:00Z',
      success_rate: 100.0
    }
  },
  {
    id: 'rule-cve-kernel-patch',
    name: 'Automated Patching for Critical CVE Vulnerability',
    description: 'Triggered when Security Sentinel / Wiz detects CVSS > 9.0 kernel vulnerability on non-prod nodes.',
    enabled: false,
    trigger: {
      type: 'kafka_event',
      source: 'secops-cve-stream',
      event_name: 'security.cve.critical_published',
      criteria: [
        { field: 'cvss_score', operator: '>=', value: '9.0' },
        { field: 'environment', operator: 'in', value: 'DEV,UAT' }
      ]
    },
    action: {
      identifier: 'os-rhel-kernel-patch',
      name: 'RHEL 9 Security Kernel Hotpatch',
      engine: 'ansible',
      parameter_mappings: {
        target_group: '{{ trigger.payload.affected_hosts }}',
        reboot_strategy: 'graceful-rolling',
        environment: '{{ trigger.payload.environment }}'
      }
    },
    governance: {
      requires_lead_approval: false,
      auto_create_chg: true,
      cooldown_seconds: 7200
    },
    stats: {
      total_triggered: 8,
      last_triggered_at: '2026-08-28T14:10:00Z',
      success_rate: 87.5
    }
  },
  {
    id: 'rule-vpc-route-drift',
    name: 'Terraform Drift Auto-Reconciliation (AWS VPC)',
    description: 'Triggered by Firefly / CloudTrail route table drift event. Runs terraform apply in target subnet.',
    enabled: true,
    trigger: {
      type: 'kafka_event',
      source: 'cloudtrail-audit-bus',
      event_name: 'aws.ec2.RouteTableModifiedOutsideTerraform',
      criteria: [
        { field: 'drift_severity', operator: '==', value: 'HIGH' }
      ]
    },
    action: {
      identifier: 'cloud-aws-vpc-peering',
      name: 'AWS VPC Peering & Route Sync',
      engine: 'terraform',
      parameter_mappings: {
        region: 'us-east-1',
        vpc_id: '{{ trigger.payload.vpc_id }}',
        target_cidr: '10.200.0.0/16',
        environment: 'PROD'
      }
    },
    governance: {
      requires_lead_approval: true,
      auto_create_chg: true,
      cooldown_seconds: 600
    },
    stats: {
      total_triggered: 31,
      last_triggered_at: '2026-09-05T22:05:14Z',
      success_rate: 96.8
    }
  }
];

function RulesContent() {
  const [rules, setRules] = useState<AutomationRule[]>(PRESET_RULES);
  const [selectedId, setSelectedId] = useState<string>(PRESET_RULES[0].id);
  const [search, setSearch] = useState('');
  const [simulateSuccess, setSimulateSuccess] = useState<string | null>(null);

  const filteredRules = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return rules;
    return rules.filter(
      (r) =>
        r.name.toLowerCase().includes(q) ||
        r.description.toLowerCase().includes(q) ||
        r.trigger.event_name.toLowerCase().includes(q) ||
        r.action.identifier.toLowerCase().includes(q)
    );
  }, [rules, search]);

  const activeRule = useMemo(() => rules.find((r) => r.id === selectedId) ?? rules[0], [rules, selectedId]);

  const toggleRule = (id: string) => {
    setRules((prev) =>
      prev.map((r) => (r.id === id ? { ...r, enabled: !r.enabled } : r))
    );
  };

  const runSimulation = () => {
    setSimulateSuccess(`[SIMULATED] Trigger event emitted for ${activeRule.trigger.event_name}. Matched criteria! Execution job queued.`);
    setTimeout(() => setSimulateSuccess(null), 5000);
  };

  return (
    <div className="flex h-full">
      {/* MASTER LIST (Left Panel: 380px) */}
      <div className="w-[380px] flex-shrink-0 border-r border-glass-border flex flex-col bg-glass-surface/30">
        <div className="p-3 border-b border-glass-border flex items-center justify-between gap-2">
          <div className="relative flex-1">
            <Search size={14} className="absolute left-2.5 top-2.5 text-slate-500" />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Filter rules, triggers, actions..."
              className="w-full pl-8 pr-3 py-1.5 rounded-lg bg-glass-surface border border-glass-border text-xs text-slate-200 placeholder-slate-600 outline-none focus:border-cyan-500/40"
            />
          </div>
          <button
            onClick={() => alert('New Rule Builder (YAML / Visual Workflow) modal is ready')}
            className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg bg-cyan-500/10 border border-cyan-500/30 text-cyan-400 text-xs font-mono hover:bg-cyan-500/20"
          >
            <Plus size={14} />
            <span>New</span>
          </button>
        </div>

        {/* Rule Cards */}
        <div className="flex-1 overflow-y-auto divide-y divide-glass-border/40">
          {filteredRules.map((rule) => (
            <button
              key={rule.id}
              onClick={() => setSelectedId(rule.id)}
              className={`w-full text-left p-3.5 transition-colors relative flex flex-col gap-1.5 ${
                selectedId === rule.id ? 'bg-cyan-500/[0.08]' : 'hover:bg-white/[0.02]'
              }`}
            >
              {selectedId === rule.id && (
                <div className="absolute left-0 top-0 bottom-0 w-[3px] bg-cyan-400 rounded-r" />
              )}
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className={`w-2 h-2 rounded-full ${rule.enabled ? 'bg-emerald-400 shadow-glow-emerald' : 'bg-slate-600'}`} />
                  <span className="text-xs font-semibold text-slate-200 truncate max-w-[230px]">{rule.name}</span>
                </div>
                <span className={`text-[10px] font-mono px-1.5 py-0.5 rounded border ${
                  rule.enabled
                    ? 'border-emerald-500/30 text-emerald-400 bg-emerald-500/10'
                    : 'border-slate-700 text-slate-500 bg-slate-800/40'
                }`}>
                  {rule.enabled ? 'ACTIVE' : 'MUTED'}
                </span>
              </div>
              <div className="text-[11px] text-slate-500 line-clamp-2">
                {rule.description}
              </div>
              <div className="flex items-center gap-2 mt-1 text-[10px] font-mono text-slate-600">
                <span className="text-cyan-400/80">{rule.trigger.type}</span>
                <span>→</span>
                <span className="text-slate-400 truncate">{rule.action.identifier}</span>
              </div>
            </button>
          ))}
        </div>
      </div>

      {/* DETAIL PANE (Right Panel) */}
      <div className="flex-1 overflow-y-auto p-6">
        {activeRule && (
          <div className="max-w-3xl mx-auto space-y-6">
            {/* Header */}
            <div className="flex items-start justify-between">
              <div>
                <div className="flex items-center gap-3">
                  <h1 className="text-lg font-bold text-slate-100">{activeRule.name}</h1>
                  <span className={`px-2 py-0.5 rounded text-[11px] font-mono border ${
                    activeRule.enabled
                      ? 'border-emerald-500/40 bg-emerald-500/10 text-emerald-400'
                      : 'border-slate-700 bg-slate-800 text-slate-500'
                  }`}>
                    {activeRule.enabled ? 'AUTOMATION ENABLED' : 'RULE PAUSED'}
                  </span>
                </div>
                <p className="text-xs text-slate-400 mt-1">{activeRule.description}</p>
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => toggleRule(activeRule.id)}
                  className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg border text-xs font-mono transition-colors ${
                    activeRule.enabled
                      ? 'border-amber-500/30 text-amber-300 bg-amber-500/10 hover:bg-amber-500/20'
                      : 'border-emerald-500/30 text-emerald-400 bg-emerald-500/10 hover:bg-emerald-500/20'
                  }`}
                >
                  {activeRule.enabled ? <ToggleRight size={16} /> : <ToggleLeft size={16} />}
                  <span>{activeRule.enabled ? 'Pause Rule' : 'Activate Rule'}</span>
                </button>
                <button
                  onClick={runSimulation}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-cyan-500/40 bg-cyan-500/10 text-cyan-300 text-xs font-mono hover:bg-cyan-500/20"
                >
                  <Play size={13} />
                  <span>Simulate Trigger</span>
                </button>
              </div>
            </div>

            {simulateSuccess && (
              <div className="p-3 rounded-lg bg-cyan-950/40 border border-cyan-500/30 text-cyan-300 text-xs font-mono flex items-center gap-2">
                <CheckCircle2 size={16} className="text-cyan-400 flex-shrink-0" />
                <span>{simulateSuccess}</span>
              </div>
            )}

            {/* Visual Workflow Orchestration Flow: Trigger -> Filter -> Action -> Governance */}
            <div className="space-y-4">
              {/* STEP 1: TRIGGER SPECIFICATION */}
              <div className="p-4 rounded-xl bg-glass-surface border border-glass-border relative">
                <div className="flex items-center gap-2 text-xs font-mono text-cyan-400 mb-2">
                  <Bell size={14} />
                  <span className="uppercase tracking-wider">Step 1: Event Trigger</span>
                </div>
                <div className="grid grid-cols-2 gap-4 text-xs font-mono">
                  <div>
                    <span className="text-slate-500">Trigger Source:</span>
                    <div className="text-slate-300 mt-0.5">{activeRule.trigger.source}</div>
                  </div>
                  <div>
                    <span className="text-slate-500">Event Topic / Metric:</span>
                    <div className="text-slate-300 mt-0.5">{activeRule.trigger.event_name}</div>
                  </div>
                </div>
              </div>

              {/* ARROW */}
              <div className="flex justify-center text-slate-600">
                <ArrowRight className="rotate-90" size={16} />
              </div>

              {/* STEP 2: CRITERIA & FILTERS */}
              <div className="p-4 rounded-xl bg-glass-surface border border-glass-border">
                <div className="flex items-center gap-2 text-xs font-mono text-amber-400 mb-2">
                  <Filter size={14} />
                  <span className="uppercase tracking-wider">Step 2: Gate & Filter Criteria</span>
                </div>
                <div className="space-y-1.5">
                  {activeRule.trigger.criteria.map((c, idx) => (
                    <div key={idx} className="flex items-center gap-2 text-xs font-mono bg-canvas-void/80 p-2 rounded border border-glass-border">
                      <span className="text-slate-400">{c.field}</span>
                      <span className="text-amber-400 font-bold">{c.operator}</span>
                      <span className="text-cyan-300">"{c.value}"</span>
                    </div>
                  ))}
                </div>
              </div>

              {/* ARROW */}
              <div className="flex justify-center text-slate-600">
                <ArrowRight className="rotate-90" size={16} />
              </div>

              {/* STEP 3: ACTION & PARAMETER MAPPING */}
              <div className="p-4 rounded-xl bg-glass-surface border border-glass-border">
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2 text-xs font-mono text-emerald-400">
                    <Zap size={14} />
                    <span className="uppercase tracking-wider">Step 3: Action Execution</span>
                  </div>
                  <span className="text-xs font-mono text-slate-400">Runner: {activeRule.action.engine}</span>
                </div>
                <div className="text-xs font-mono text-slate-200 mb-3">
                  <span className="text-cyan-400 font-semibold">{activeRule.action.identifier}</span>
                  <span className="text-slate-500 ml-2">({activeRule.action.name})</span>
                </div>

                <div className="space-y-1 bg-canvas-void p-3 rounded-lg border border-glass-border text-xs font-mono">
                  <div className="text-[10px] text-slate-500 mb-1.5 uppercase">Jinja2 Parameter Interpolation</div>
                  {Object.entries(activeRule.action.parameter_mappings).map(([param, mapping]) => (
                    <div key={param} className="flex items-center justify-between py-0.5">
                      <span className="text-slate-400">{param}:</span>
                      <span className="text-cyan-300 font-mono">{mapping}</span>
                    </div>
                  ))}
                </div>
              </div>

              {/* ARROW */}
              <div className="flex justify-center text-slate-600">
                <ArrowRight className="rotate-90" size={16} />
              </div>

              {/* STEP 4: GOVERNANCE & SOX/MAKER-CHECKER GATES */}
              <div className="p-4 rounded-xl bg-glass-surface border border-glass-border">
                <div className="flex items-center gap-2 text-xs font-mono text-purple-400 mb-2">
                  <Shield size={14} />
                  <span className="uppercase tracking-wider">Step 4: Enterprise Governance & Change Approval</span>
                </div>
                <div className="grid grid-cols-3 gap-3 text-xs font-mono">
                  <div className="p-2.5 rounded bg-canvas-void border border-glass-border">
                    <span className="text-slate-500 block text-[10px]">MAKER-CHECKER:</span>
                    <span className={activeRule.governance.requires_lead_approval ? 'text-amber-400' : 'text-slate-400'}>
                      {activeRule.governance.requires_lead_approval ? 'Dual-Signoff Required' : 'Pre-approved Auto'}
                    </span>
                  </div>
                  <div className="p-2.5 rounded bg-canvas-void border border-glass-border">
                    <span className="text-slate-500 block text-[10px]">SERVICENOW CHG:</span>
                    <span className={activeRule.governance.auto_create_chg ? 'text-purple-400' : 'text-slate-400'}>
                      {activeRule.governance.auto_create_chg ? 'Auto-Register Ticket' : 'Manual'}
                    </span>
                  </div>
                  <div className="p-2.5 rounded bg-canvas-void border border-glass-border">
                    <span className="text-slate-500 block text-[10px]">COOLDOWN GUARD:</span>
                    <span className="text-slate-300">{activeRule.governance.cooldown_seconds}s interval</span>
                  </div>
                </div>
              </div>
            </div>

            {/* Execution Telemetry Stats */}
            <div className="p-4 rounded-xl bg-glass-surface border border-glass-border">
              <h3 className="text-xs font-mono text-slate-500 uppercase tracking-wider mb-3">Live Telemetry & Firing History</h3>
              <div className="grid grid-cols-3 gap-4 text-xs font-mono">
                <div>
                  <span className="text-slate-500">Total Invocations</span>
                  <div className="text-lg font-bold text-slate-200 mt-1">{activeRule.stats.total_triggered}</div>
                </div>
                <div>
                  <span className="text-slate-500">Execution Success Rate</span>
                  <div className="text-lg font-bold text-emerald-400 mt-1">{activeRule.stats.success_rate}%</div>
                </div>
                <div>
                  <span className="text-slate-500">Last Triggered</span>
                  <div className="text-xs text-slate-300 mt-2 font-mono">
                    {activeRule.stats.last_triggered_at ? new Date(activeRule.stats.last_triggered_at).toLocaleString() : 'Never'}
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default function RulesPage() {
  return (
    <AppShell>
      <RulesContent />
    </AppShell>
  );
}

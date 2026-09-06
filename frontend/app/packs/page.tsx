'use client';

import React, { useState, useMemo } from 'react';
import {
  Package, Search, ShieldCheck, ExternalLink, GitBranch,
  CheckCircle2, Download, RefreshCw, Layers, Zap, Terminal,
  Network, Cloud, Database, Monitor, Shield, Boxes, Settings, ArrowRight
} from 'lucide-react';
import { AppShell } from '@/components/layout/AppShell';
import { useRouter } from 'next/navigation';

interface PackItem {
  id: string;
  name: string;
  version: string;
  category: string;
  author: string;
  repository: string;
  description: string;
  installed: boolean;
  actions_count: number;
  rules_count: number;
  engine_support: string[];
  status: 'HEALTHY' | 'UPDATE_AVAILABLE' | 'UNCONFIGURED';
  dependencies: { name: string; version: string; satisfied: boolean }[];
  actions: { identifier: string; name: string; engine: string; risk: string }[];
}

const PACKS_CATALOG: PackItem[] = [
  {
    id: 'pack-openclaw-infra',
    name: 'openclaw-infrastructure-bundle',
    version: '2.0.0',
    category: 'infrastructure',
    author: 'OpenClaw & Vulcan Architecture Community',
    repository: 'local://content-packs/openclaw-infrastructure-bundle',
    description: 'Hermetic, offline-ready Ansible Content Pack combining OpenClaw Agent, PostgreSQL 16, Jenkins CI/CD, GitLab CE, Docker Engine, and Linux System Hardening.',
    installed: true,
    actions_count: 10,
    rules_count: 4,
    engine_support: ['ansible'],
    status: 'HEALTHY',
    dependencies: [
      { name: 'ansible.posix', version: '>=1.5.0', satisfied: true },
      { name: 'community.general', version: '>=8.0.0', satisfied: true },
      { name: 'community.crypto', version: '>=2.15.0', satisfied: true }
    ],
    actions: [
      { identifier: 'claw-openclaw-deploy', name: 'OpenClaw Hardened Bot & Agent Deployment', engine: 'ansible', risk: 'MEDIUM' },
      { identifier: 'infra-docker-setup', name: 'Docker CE Runtime & Container Daemon Provisioning', engine: 'ansible', risk: 'MEDIUM' },
      { identifier: 'db-postgres-provision', name: 'PostgreSQL Cluster Deployment & Database Provisioning', engine: 'ansible', risk: 'HIGH' },
      { identifier: 'ci-jenkins-deploy', name: 'Jenkins CI/CD Automation Server Deployment', engine: 'ansible', risk: 'MEDIUM' },
      { identifier: 'git-gitlab-stage', name: 'GitLab Enterprise CE/EE Infrastructure Setup', engine: 'ansible', risk: 'HIGH' },
      { identifier: 'k8s-node-provision', name: 'Kubernetes Node Provisioning & Container Runtime Setup', engine: 'ansible', risk: 'HIGH' },
      { identifier: 'web-nginx-deploy', name: 'High-Performance Nginx Web Server & Reverse Proxy', engine: 'ansible', risk: 'LOW' },
      { identifier: 'cache-redis-deploy', name: 'Redis In-Memory Cache & Key-Value Store Deployment', engine: 'ansible', risk: 'MEDIUM' },
      { identifier: 'sec-system-hardening', name: 'Linux Server Security Hardening & SSH Audit Policy', engine: 'ansible', risk: 'MEDIUM' },
      { identifier: 'os-sandbox-ping', name: 'Sandbox Ping & Facts Gathering Probe', engine: 'ansible', risk: 'LOW' }
    ]
  },
  {
    id: 'pack-network',
    name: 'network-enterprise',
    version: '1.4.2',
    category: 'network',
    author: 'infra-network-core@pnc.com',
    repository: 'https://github.com/vulcan-packs/network-enterprise',
    description: 'F5 BIG-IP LTM/GTM automation, Cisco Nexus NX-OS ACLs, Palo Alto Panorama next-gen firewall rules.',
    installed: true,
    actions_count: 12,
    rules_count: 3,
    engine_support: ['ansible'],
    status: 'HEALTHY',
    dependencies: [
      { name: 'ansible.netcommon', version: '>=5.1.0', satisfied: true },
      { name: 'f5networks.f5_modules', version: '>=1.28.0', satisfied: true },
      { name: 'cisco.nxos', version: '>=4.2.0', satisfied: true }
    ],
    actions: [
      { identifier: 'net-f5-cert-renew', name: 'F5 SSL Certificate ACME Renewal', engine: 'ansible', risk: 'HIGH' },
      { identifier: 'net-f5-vip-create', name: 'F5 Virtual Server & Pool Member Provisioning', engine: 'ansible', risk: 'MEDIUM' },
      { identifier: 'net-cisco-acl-update', name: 'Cisco Nexus Core Switch ACL Modification', engine: 'ansible', risk: 'HIGH' },
      { identifier: 'net-palo-fw-rule-add', name: 'Palo Alto Security Zone Rule Whitelist', engine: 'ansible', risk: 'HIGH' }
    ]
  },
  {
    id: 'pack-cloud',
    name: 'cloud-aws-azure',
    version: '2.1.0',
    category: 'cloud',
    author: 'cloud-infra-team@pnc.com',
    repository: 'https://github.com/vulcan-packs/cloud-aws-azure',
    description: 'Multi-cloud Terraform modules for AWS VPC Peering, Transit Gateway, Azure ExpressRoute, and IAM Role governance.',
    installed: true,
    actions_count: 18,
    rules_count: 5,
    engine_support: ['terraform'],
    status: 'HEALTHY',
    dependencies: [
      { name: 'hashicorp/aws', version: '~> 5.30', satisfied: true },
      { name: 'hashicorp/azurerm', version: '~> 3.85', satisfied: true }
    ],
    actions: [
      { identifier: 'cloud-aws-vpc-peering', name: 'AWS Cross-Account VPC Peering', engine: 'terraform', risk: 'HIGH' },
      { identifier: 'cloud-eks-nodegroup-scale', name: 'AWS EKS Managed Node Group Autoscaling', engine: 'terraform', risk: 'MEDIUM' },
      { identifier: 'cloud-s3-kms-encryption', name: 'S3 Bucket SSE-KMS Policy Enforcement', engine: 'terraform', risk: 'LOW' }
    ]
  },
  {
    id: 'pack-database',
    name: 'database-tier1',
    version: '1.2.0',
    category: 'database',
    author: 'db-sre@pnc.com',
    repository: 'https://github.com/vulcan-packs/database-tier1',
    description: 'Mission-critical database operations for Oracle Exadata, PostgreSQL 16 High Availability, and Redis Cluster.',
    installed: true,
    actions_count: 8,
    rules_count: 2,
    engine_support: ['ansible', 'terraform'],
    status: 'HEALTHY',
    dependencies: [
      { name: 'oracle.cx_oracle', version: '>=8.3.0', satisfied: true },
      { name: 'community.postgresql', version: '>=3.1.0', satisfied: true }
    ],
    actions: [
      { identifier: 'db-oracle-tablespace-expand', name: 'Oracle Exadata Storage Tablespace Expansion', engine: 'ansible', risk: 'HIGH' },
      { identifier: 'db-postgres-vacuum-analyze', name: 'PostgreSQL 16 Multi-Tenant Autovacuum Run', engine: 'ansible', risk: 'LOW' },
      { identifier: 'db-redis-cluster-failover', name: 'Redis Enterprise Managed Quorum Failover', engine: 'ansible', risk: 'HIGH' }
    ]
  },
  {
    id: 'pack-k8s',
    name: 'k8s-platform-governance',
    version: '2.0.1',
    category: 'kubernetes',
    author: 'platform-engineering@pnc.com',
    repository: 'https://github.com/vulcan-packs/k8s-platform-governance',
    description: 'Kubernetes operational tasks: cluster drainage, pod disruption budget reconciliation, cert-manager rotations.',
    installed: true,
    actions_count: 9,
    rules_count: 4,
    engine_support: ['ansible'],
    status: 'HEALTHY',
    dependencies: [
      { name: 'kubernetes.core', version: '>=2.4.0', satisfied: true }
    ],
    actions: [
      { identifier: 'k8s-cluster-node-drain', name: 'Graceful Kubernetes Worker Node Drain', engine: 'ansible', risk: 'HIGH' },
      { identifier: 'k8s-ingress-cert-rotate', name: 'Cert-Manager Ingress TLS Rotation', engine: 'ansible', risk: 'MEDIUM' }
    ]
  },
  {
    id: 'pack-os',
    name: 'os-patching-fleet',
    version: '1.0.3',
    category: 'os_patching',
    author: 'sysops-patching@pnc.com',
    repository: 'https://github.com/vulcan-packs/os-patching-fleet',
    description: 'Automated patch baseline management, kernel vulnerability hotpatching, and reboot coordination across 10,000+ servers.',
    installed: true,
    actions_count: 6,
    rules_count: 1,
    engine_support: ['ansible'],
    status: 'HEALTHY',
    dependencies: [
      { name: 'ansible.posix', version: '>=1.5.0', satisfied: true }
    ],
    actions: [
      { identifier: 'os-rhel-kernel-patch', name: 'RHEL 9 Security Kernel Hotpatch', engine: 'ansible', risk: 'HIGH' },
      { identifier: 'os-fleet-uptime-audit', name: 'Enterprise Fleet Reboot & Uptime Audit', engine: 'ansible', risk: 'LOW' }
    ]
  }
];

const CATEGORY_ICONS: Record<string, React.ReactNode> = {
  network: <Network size={16} />,
  cloud: <Cloud size={16} />,
  database: <Database size={16} />,
  kubernetes: <Boxes size={16} />,
  os_patching: <Monitor size={16} />,
  security: <Shield size={16} />,
  infrastructure: <Layers size={16} />
};

function PacksContent() {
  const router = useRouter();
  const [packs] = useState<PackItem[]>(PACKS_CATALOG);
  const [selectedId, setSelectedId] = useState<string>(PACKS_CATALOG[0].id);
  const [search, setSearch] = useState('');

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return packs;
    return packs.filter((p) =>
      p.name.toLowerCase().includes(q) ||
      p.category.toLowerCase().includes(q) ||
      p.description.toLowerCase().includes(q)
    );
  }, [packs, search]);

  const activePack = useMemo(() => packs.find((p) => p.id === selectedId) ?? packs[0], [packs, selectedId]);

  return (
    <div className="flex h-full">
      {/* PACK LIST (Left Panel) */}
      <div className="w-[360px] flex-shrink-0 border-r border-glass-border flex flex-col bg-glass-surface/30">
        <div className="p-3 border-b border-glass-border flex items-center justify-between gap-2">
          <div className="relative flex-1">
            <Search size={14} className="absolute left-2.5 top-2.5 text-slate-500" />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search content packs & plugins..."
              className="w-full pl-8 pr-3 py-1.5 rounded-lg bg-glass-surface border border-glass-border text-xs text-slate-200 placeholder-slate-600 outline-none focus:border-cyan-500/40"
            />
          </div>
          <button
            onClick={() => alert('Syncing packs with Git remote registry…')}
            className="p-1.5 rounded-lg border border-glass-border bg-glass-surface text-slate-400 hover:text-cyan-300"
            title="Sync registry"
          >
            <RefreshCw size={14} />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto divide-y divide-glass-border/40">
          {filtered.map((pack) => (
            <button
              key={pack.id}
              onClick={() => setSelectedId(pack.id)}
              className={`w-full text-left p-3.5 transition-colors relative flex flex-col gap-1.5 ${
                selectedId === pack.id ? 'bg-cyan-500/[0.08]' : 'hover:bg-white/[0.02]'
              }`}
            >
              {selectedId === pack.id && (
                <div className="absolute left-0 top-0 bottom-0 w-[3px] bg-cyan-400 rounded-r" />
              )}
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="text-cyan-400">{CATEGORY_ICONS[pack.category] ?? <Package size={16} />}</span>
                  <span className="text-xs font-bold font-mono text-slate-200">{pack.name}</span>
                </div>
                <span className="text-[10px] font-mono text-slate-500">v{pack.version}</span>
              </div>
              <div className="text-[11px] text-slate-500 line-clamp-2">
                {pack.description}
              </div>
              <div className="flex items-center gap-3 text-[10px] font-mono text-slate-600 mt-1">
                <span>{pack.actions_count} Actions</span>
                <span>•</span>
                <span>{pack.rules_count} Rules</span>
                <span className="ml-auto text-emerald-400 flex items-center gap-1">
                  <CheckCircle2 size={10} />
                  HEALTHY
                </span>
              </div>
            </button>
          ))}
        </div>
      </div>

      {/* DETAIL PANE (Right Panel) */}
      <div className="flex-1 overflow-y-auto p-6">
        {activePack && (
          <div className="max-w-3xl mx-auto space-y-6">
            {/* Header Card */}
            <div className="p-5 rounded-xl bg-glass-surface border border-glass-border space-y-3">
              <div className="flex items-start justify-between">
                <div className="flex items-center gap-3">
                  <div className="p-2.5 rounded-lg bg-cyan-500/10 border border-cyan-500/20 text-cyan-400">
                    {CATEGORY_ICONS[activePack.category] ?? <Package size={24} />}
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <h1 className="text-base font-bold font-mono text-slate-100">{activePack.name}</h1>
                      <span className="text-[11px] font-mono px-2 py-0.5 rounded border border-cyan-500/30 bg-cyan-950/40 text-cyan-400">
                        v{activePack.version}
                      </span>
                    </div>
                    <p className="text-xs text-slate-400 mt-0.5">{activePack.description}</p>
                  </div>
                </div>
                <span className="text-xs font-mono px-2 py-1 rounded border border-emerald-500/30 bg-emerald-500/10 text-emerald-400 flex items-center gap-1">
                  <CheckCircle2 size={12} />
                  INSTALLED
                </span>
              </div>

              <div className="grid grid-cols-3 gap-3 pt-3 border-t border-glass-border text-xs font-mono text-slate-400">
                <div>
                  <span className="text-slate-600 block text-[10px]">MAINTAINER:</span>
                  <span className="text-slate-300">{activePack.author}</span>
                </div>
                <div>
                  <span className="text-slate-600 block text-[10px]">SUPPORTED RUNNERS:</span>
                  <span className="text-cyan-400">{activePack.engine_support.join(', ')}</span>
                </div>
                <div>
                  <span className="text-slate-600 block text-[10px]">REPOSITORY:</span>
                  <a href={activePack.repository} target="_blank" rel="noreferrer" className="text-cyan-400 hover:underline flex items-center gap-1">
                    <span>Git Source</span>
                    <ExternalLink size={10} />
                  </a>
                </div>
              </div>
            </div>

            {/* Actions in this Pack */}
            <div className="p-5 rounded-xl bg-glass-surface border border-glass-border space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2 text-xs font-mono text-slate-300">
                  <Zap size={15} className="text-cyan-400" />
                  <span className="font-bold uppercase tracking-wider">Playbooks & Actions in this Pack ({activePack.actions.length})</span>
                </div>
              </div>

              <div className="divide-y divide-glass-border/40">
                {activePack.actions.map((act) => (
                  <div key={act.identifier} className="py-2.5 flex items-center justify-between">
                    <div>
                      <div className="text-xs font-mono text-slate-200">{act.identifier}</div>
                      <div className="text-[11px] text-slate-500">{act.name}</div>
                    </div>
                    <div className="flex items-center gap-3">
                      <span className="text-[10px] font-mono px-1.5 py-0.5 rounded border border-slate-700 text-slate-400">
                        {act.engine}
                      </span>
                      <span className={`text-[10px] font-mono px-1.5 py-0.5 rounded border ${
                        act.risk === 'HIGH' ? 'border-rose-500/30 text-rose-400 bg-rose-500/10' :
                        act.risk === 'MEDIUM' ? 'border-amber-500/30 text-amber-400 bg-amber-500/10' :
                        'border-emerald-500/30 text-emerald-400 bg-emerald-500/10'
                      }`}>
                        {act.risk}
                      </span>
                      <button
                        onClick={() => router.push(`/actions?selected=${encodeURIComponent(act.identifier)}`)}
                        className="flex items-center gap-1 px-2.5 py-1 rounded bg-cyan-500/10 border border-cyan-500/30 text-cyan-400 text-xs font-mono hover:bg-cyan-500/20"
                      >
                        <span>Open & Run</span>
                        <ArrowRight size={11} />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Dependency Validation */}
            <div className="p-5 rounded-xl bg-glass-surface border border-glass-border space-y-3">
              <div className="flex items-center gap-2 text-xs font-mono text-slate-300">
                <ShieldCheck size={15} className="text-emerald-400" />
                <span className="font-bold uppercase tracking-wider">Execution Engine & Module Dependencies</span>
              </div>
              <div className="space-y-2">
                {activePack.dependencies.map((dep, i) => (
                  <div key={i} className="flex items-center justify-between p-2.5 rounded-lg bg-canvas-void/80 border border-glass-border text-xs font-mono">
                    <span className="text-slate-300">{dep.name} ({dep.version})</span>
                    <span className="text-emerald-400 flex items-center gap-1">
                      <CheckCircle2 size={12} />
                      Satisfied
                    </span>
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

export default function PacksPage() {
  return (
    <AppShell>
      <PacksContent />
    </AppShell>
  );
}

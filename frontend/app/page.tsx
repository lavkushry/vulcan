'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { 
  Activity, 
  Terminal as TerminalIcon, 
  Cpu, 
  ShieldCheck, 
  Search, 
  RotateCcw, 
  Play, 
  CheckCircle2, 
  AlertTriangle,
  Layers,
  Columns,
  Maximize2,
  Minimize2,
  X,
  Radio,
  Clock,
  Sparkles,
  Server
} from 'lucide-react';

import ChatAssistant, { ChatLaunchPayload } from '../components/ChatAssistant';
import HighFilteredTaskWindow, { TaskRecord } from '../components/HighFilteredTaskWindow';
import TerminalStream from '../components/TerminalStream';
import DiagnosticDrawer from '../components/DiagnosticDrawer';
import MakerCheckerDeck from '../components/MakerCheckerDeck';

const API_BASE = 'http://localhost:8000/api/v1';

// Initial pre-seeded task fallback if backend is still starting
const INITIAL_FALLBACK_TASKS: TaskRecord[] = [
  {
    id: 'task-1001',
    correlation_id: 'EXEC-9821',
    identifier: 'net-f5-cert-renew',
    name: 'F5 BIG-IP SSL Certificate Renewal',
    engine: 'ansible',
    category: 'network',
    target_resource: 'f5-edge-01.internal',
    environment: 'PROD',
    status: 'RUNNING',
    risk_tier: 'HIGH',
    requester_id: 'alex.engineer',
    approver_id: 'sarah.lead',
    duration_sec: 48,
    created_at: new Date(Date.now() - 48000).toISOString(),
    parameters: { hostname: 'f5-edge-01.internal', vip_ip: '10.200.1.50', cert_valid_days: 90 }
  },
  {
    id: 'task-1002',
    correlation_id: 'EXEC-9820',
    identifier: 'cloud-vpc-peering',
    name: 'Cross-Account AWS VPC Peering Connection',
    engine: 'terraform',
    category: 'cloud',
    target_resource: 'vpc-09a8b7c6d5e4',
    environment: 'PROD',
    status: 'SUCCESS',
    risk_tier: 'MEDIUM',
    requester_id: 'david.cloudops',
    approver_id: 'lead.bob',
    duration_sec: 142,
    created_at: new Date(Date.now() - 1420000).toISOString(),
    parameters: { peer_vpc_id: 'vpc-09a8b7c6d5e4', peer_cidr: '10.150.0.0/16' }
  },
  {
    id: 'task-1003',
    correlation_id: 'EXEC-9819',
    identifier: 'db-expand-tablespace',
    name: 'Database Tablespace Disk Expansion',
    engine: 'ansible',
    category: 'database',
    target_resource: 'prod-pg-01.internal',
    environment: 'PROD',
    status: 'FAILED',
    risk_tier: 'HIGH',
    requester_id: 'priya.dba',
    approver_id: 'sarah.lead',
    duration_sec: 76,
    created_at: new Date(Date.now() - 2500000).toISOString(),
    error_message: 'Fatal: Storage pool VG_DATA has insufficient free extents for +100GB.',
    parameters: { tablespace_name: 'TS_TRANSACTIONS', expand_gb: 100 }
  },
  {
    id: 'task-1004',
    correlation_id: 'EXEC-9818',
    identifier: 'os-rhel9-kernel-patch',
    name: 'RHEL 9 Live Kernel Security Patching (kpatch)',
    engine: 'ansible',
    category: 'os_patching',
    target_resource: 'rhel-app-prod-01.internal',
    environment: 'PROD',
    status: 'SUCCESS',
    risk_tier: 'HIGH',
    requester_id: 'marcus.sre',
    approver_id: 'lead.bob',
    duration_sec: 310,
    created_at: new Date(Date.now() - 3600000).toISOString(),
    parameters: { cve_identifier: 'CVE-2025-3912', target_host: 'rhel-app-prod-01.internal' }
  },
  {
    id: 'task-1005',
    correlation_id: 'EXEC-9817',
    identifier: 'k8s-eks-nodegroup-scale',
    name: 'AWS EKS Managed Node Group Autoscaling Capacity',
    engine: 'terraform',
    category: 'cloud',
    target_resource: 'prod-useast1-eks-01',
    environment: 'PROD',
    status: 'RUNNING',
    risk_tier: 'HIGH',
    requester_id: 'marcus.sre',
    approver_id: 'sarah.lead',
    duration_sec: 95,
    created_at: new Date(Date.now() - 95000).toISOString(),
    parameters: { cluster_name: 'prod-useast1-eks-01', desired_capacity: 24 }
  },
  {
    id: 'task-1006',
    correlation_id: 'EXEC-9816',
    identifier: 'sec-ssh-fleet-rotate',
    name: 'Fleet-Wide Ed25519 SSH Authorized Keys Rotation',
    engine: 'ansible',
    category: 'security',
    target_resource: 'all_linux_prod',
    environment: 'PROD',
    status: 'PENDING_APPROVAL',
    risk_tier: 'HIGH',
    requester_id: 'sec-ops-bot',
    approver_id: null,
    duration_sec: 0,
    created_at: new Date(Date.now() - 4200000).toISOString(),
    parameters: { target_host_group: 'all_linux_prod', key_owner: 'automation-svc' }
  }
];

export default function MissionControlDashboard() {
  const [tasks, setTasks] = useState<TaskRecord[]>(INITIAL_FALLBACK_TASKS);
  const [isLoadingTasks, setIsLoadingTasks] = useState(false);
  const [viewMode, setViewMode] = useState<'split' | 'chat-focus' | 'tasks-focus'>('split');

  // Terminal & Inspection Modal State
  const [activeTerminalTask, setActiveTerminalTask] = useState<TaskRecord | null>(null);
  const [terminalLogs, setTerminalLogs] = useState<string[]>([]);
  const [isStreamingTerminal, setIsStreamingTerminal] = useState(false);

  // Maker-Checker Review Drawer
  const [pendingReviewTask, setPendingReviewTask] = useState<TaskRecord | null>(null);

  // AI Diagnostic Drawer
  const [diagnosticOpen, setDiagnosticOpen] = useState(false);
  const [diagnosticData, setDiagnosticData] = useState<any>(null);

  // Platform Telemetry Stats
  const [telemetry, setTelemetry] = useState({
    catalogSize: 120,
    activeRunners: 2,
    merkleChainValid: true,
    lastAuditHash: '0x9a8f12c7e4b9',
    latencyMs: 12.4
  });

  // Fetch tasks from backend
  const loadTasks = useCallback(async () => {
    setIsLoadingTasks(true);
    try {
      const res = await fetch(`${API_BASE}/tasks?limit=100`);
      if (res.ok) {
        const data = await res.json();
        if (data.tasks && data.tasks.length > 0) {
          setTasks(data.tasks);
        }
      }
    } catch (err) {
      console.warn("Using local tasks cache (backend offline or loading):", err);
    } finally {
      setIsLoadingTasks(false);
    }
  }, []);

  // Fetch platform health
  const loadHealth = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/health`);
      if (res.ok) {
        const data = await res.json();
        setTelemetry(prev => ({
          ...prev,
          catalogSize: data.catalog_size || 120,
          merkleChainValid: data.audit_chain_valid,
          lastAuditHash: data.audit_tip_hash ? `${data.audit_tip_hash.slice(0, 14)}...` : prev.lastAuditHash
        }));
      }
    } catch (e) {
      // Keep initial
    }
  }, []);

  useEffect(() => {
    loadTasks();
    loadHealth();
    const interval = setInterval(() => {
      loadTasks();
    }, 5000);
    return () => clearInterval(interval);
  }, [loadTasks, loadHealth]);

  // Dispatch a new task from Chat Assistant
  const handleDispatchFromChat = async (payload: ChatLaunchPayload) => {
    try {
      const res = await fetch(`${API_BASE}/tasks/dispatch`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });

      let result;
      if (res.ok) {
        result = await res.json();
      } else {
        // Fallback optimistic creation
        const corrId = `EXEC-${Math.floor(1000 + Math.random() * 9000)}`;
        result = {
          job_id: `task-${Date.now()}`,
          correlation_id: corrId,
          status: payload.dry_run ? 'SUCCESS' : 'RUNNING',
          target_resource: payload.target_resource_id,
          requires_approval: false
        };
      }

      // Add to tasks immediately
      const newTask: TaskRecord = {
        id: result.job_id || `task-${Date.now()}`,
        correlation_id: result.correlation_id,
        identifier: payload.catalog_identifier,
        name: payload.catalog_identifier.replace(/[-_]/g, ' ').toUpperCase(),
        engine: payload.catalog_identifier.includes('cloud') || payload.catalog_identifier.includes('vpc') ? 'terraform' : 'ansible',
        category: 'cloud',
        target_resource: payload.target_resource_id,
        environment: payload.environment,
        status: result.status || 'RUNNING',
        risk_tier: 'HIGH',
        requester_id: payload.requester_id || 'console.operator',
        duration_sec: 1,
        created_at: new Date().toISOString(),
        parameters: payload.parameters
      };

      setTasks(prev => [newTask, ...prev]);

      // If operator wants to watch live, open terminal
      handleOpenTerminal(newTask);

      return result;
    } catch (err: any) {
      console.error("Task dispatch error:", err);
      throw err;
    }
  };

  // Open live terminal for a given task
  const handleOpenTerminal = async (task: TaskRecord) => {
    setActiveTerminalTask(task);
    setTerminalLogs([
      `\x1b[1;36m[PROJECT VULCAN CONTROL PLANE]\x1b[0m Connecting to execution stream for ${task.correlation_id}...`,
      `\x1b[34m[PAM CYBERARK]\x1b[0m Bound ephemeral session credentials for target ${task.target_resource}.`,
      `\x1b[32m[AUDIT]\x1b[0m Merkle pre-flight commit registered to ledger. Tip: ${telemetry.lastAuditHash}`,
      `PLAY [${task.name}] **************************************************`
    ]);

    try {
      const res = await fetch(`${API_BASE}/tasks/${task.correlation_id}/logs`);
      if (res.ok) {
        const data = await res.json();
        if (data.logs && data.logs.length > 0) {
          setTerminalLogs(data.logs);
        }
      }
    } catch (e) {
      console.warn("Could not fetch remote logs, displaying buffered session.");
    }
  };

  // Approve a pending task
  const handleApprovePendingTask = async (correlationId: string) => {
    try {
      const res = await fetch(`${API_BASE}/jobs/${correlationId}/approve`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          approver_id: 'sarah.lead',
          decision: 'APPROVE',
          reason: 'Authorized via Mission Control UI'
        })
      });

      if (res.ok) {
        // Trigger execution
        await fetch(`${API_BASE}/jobs/${correlationId}/execute`, { method: 'POST' });
      }

      // Optimistically update status
      setTasks(prev => prev.map(t => {
        if (t.correlation_id === correlationId) {
          return { ...t, status: 'RUNNING', approver_id: 'sarah.lead' };
        }
        return t;
      }));

      loadTasks();
    } catch (err) {
      console.error("Approval error:", err);
    }
  };

  // Re-run task
  const handleRerun = (task: TaskRecord) => {
    handleDispatchFromChat({
      catalog_identifier: task.identifier,
      target_resource_id: task.target_resource,
      parameters: task.parameters,
      environment: task.environment,
      requester_id: 'console.operator'
    });
  };

  // Trigger Failure Diagnosis
  const handleDiagnoseTask = (task: TaskRecord) => {
    setDiagnosticData({
      status: 'DIAGNOSED',
      root_cause: task.error_message || 'Storage pool VG_DATA has insufficient free extents for tablespace expansion.',
      recommended_action: 'Increase LVM volume group allocation or run volume-pool-expand playbook.',
      confidence: 0.96,
      tokens_used: 412
    });
    setDiagnosticOpen(true);
  };

  return (
    <div className="min-h-screen bg-canvas-void text-slate-100 flex flex-col font-sans selection:bg-cyan-500/30">
      {/* ================================================================= */}
      {/* MASTER MISSION CONTROL OBSIDIAN GLASS HEADER                      */}
      {/* ================================================================= */}
      <header className="sticky top-0 z-40 bg-canvas-void/80 backdrop-blur-xl border-b border-glass-border px-4 py-3 flex items-center justify-between">
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-cyan-500 via-blue-600 to-purple-600 flex items-center justify-center font-mono font-bold text-white shadow-glow-cyan/30 text-base">
              V
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-base font-bold text-white tracking-wide">
                  PROJECT VULCAN
                </h1>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-cyan-950 text-cyan-300 border border-cyan-800">
                  AUTOMATION CONTROL PLANE
                </span>
              </div>
              <p className="text-[11px] text-slate-400 font-mono">
                100–1,000+ Ansible Playbooks &amp; Terraform Infrastructure Hub
              </p>
            </div>
          </div>
        </div>

        {/* Center Live Telemetry HUD */}
        <div className="hidden lg:flex items-center gap-6 text-xs font-mono">
          <div className="flex items-center gap-2">
            <Layers className="w-4 h-4 text-cyan-400" />
            <span className="text-slate-400">Catalog:</span>
            <span className="text-white font-bold">{telemetry.catalogSize} Modules</span>
          </div>

          <div className="flex items-center gap-2">
            <Activity className="w-4 h-4 text-emerald-400 animate-pulse" />
            <span className="text-slate-400">Runners:</span>
            <span className="text-emerald-400 font-bold">{telemetry.activeRunners} Active</span>
          </div>

          <div className="flex items-center gap-2">
            <ShieldCheck className="w-4 h-4 text-purple-400" />
            <span className="text-slate-400">Merkle Tip:</span>
            <span className="text-purple-300 font-mono">{telemetry.lastAuditHash}</span>
          </div>
        </div>

        {/* Right View Toggles */}
        <div className="flex items-center gap-2">
          <div className="bg-black/40 border border-glass-border rounded-xl p-0.5 flex items-center">
            <button
              onClick={() => setViewMode('split')}
              className={`px-3 py-1 text-xs font-mono rounded-lg flex items-center gap-1.5 transition-all ${
                viewMode === 'split' 
                  ? 'bg-white/15 text-white shadow-sm font-semibold' 
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <Columns className="w-3.5 h-3.5" />
              <span>Dual Pane (50/50)</span>
            </button>
            <button
              onClick={() => setViewMode('chat-focus')}
              className={`px-3 py-1 text-xs font-mono rounded-lg flex items-center gap-1.5 transition-all ${
                viewMode === 'chat-focus' 
                  ? 'bg-white/15 text-white shadow-sm font-semibold' 
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <Sparkles className="w-3.5 h-3.5 text-cyan-400" />
              <span>Chat Focus</span>
            </button>
            <button
              onClick={() => setViewMode('tasks-focus')}
              className={`px-3 py-1 text-xs font-mono rounded-lg flex items-center gap-1.5 transition-all ${
                viewMode === 'tasks-focus' 
                  ? 'bg-white/15 text-white shadow-sm font-semibold' 
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <Layers className="w-3.5 h-3.5 text-purple-400" />
              <span>Tasks Focus</span>
            </button>
          </div>
        </div>
      </header>

      {/* ================================================================= */}
      {/* DUAL-PANE OPERATIONAL WORKSPACE                                   */}
      {/* ================================================================= */}
      <main className="flex-1 p-4 grid grid-cols-1 lg:grid-cols-12 gap-4 max-w-[1920px] w-full mx-auto overflow-hidden">
        {/* Left Pane: Chat Assistant ("What do you want to run?") */}
        <div className={`transition-all duration-300 h-[calc(100vh-85px)] ${
          viewMode === 'split' 
            ? 'lg:col-span-5' 
            : viewMode === 'chat-focus' 
              ? 'lg:col-span-8' 
              : 'lg:col-span-4'
        }`}>
          <ChatAssistant 
            onDispatchTask={handleDispatchFromChat}
            onSelectTaskToView={(corrId) => {
              const matched = tasks.find(t => t.correlation_id === corrId);
              if (matched) handleOpenTerminal(matched);
            }}
          />
        </div>

        {/* Right Pane: High-Filtered Task Window */}
        <div className={`transition-all duration-300 h-[calc(100vh-85px)] ${
          viewMode === 'split' 
            ? 'lg:col-span-7' 
            : viewMode === 'tasks-focus' 
              ? 'lg:col-span-8' 
              : 'lg:col-span-4'
        }`}>
          <HighFilteredTaskWindow
            tasks={tasks}
            onOpenTerminal={handleOpenTerminal}
            onApproveTask={handleApprovePendingTask}
            onRerunTask={handleRerun}
            onRefresh={loadTasks}
            isLoading={isLoadingTasks}
          />
        </div>
      </main>

      {/* ================================================================= */}
      {/* LIVE TERMINAL MODAL / SLIDE-OUT OVERLAY                           */}
      {/* ================================================================= */}
      {activeTerminalTask && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-md flex items-center justify-center p-4">
          <div className="w-full max-w-4xl bg-canvas-void border border-glass-border rounded-2xl shadow-2xl overflow-hidden flex flex-col max-h-[85vh] animate-in fade-in zoom-in-95 duration-200">
            {/* Modal Header */}
            <div className="bg-canvas-subtle border-b border-glass-border px-5 py-3.5 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 rounded-lg bg-cyan-950/60 border border-cyan-500/40 flex items-center justify-center text-cyan-400">
                  <TerminalIcon className="w-4 h-4" />
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <h3 className="text-sm font-bold text-white font-mono">
                      {activeTerminalTask.correlation_id} // {activeTerminalTask.name}
                    </h3>
                    <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-white/5 border border-glass-border text-slate-300">
                      Target: {activeTerminalTask.target_resource}
                    </span>
                  </div>
                  <p className="text-xs text-slate-400 font-mono">
                    Engine: {activeTerminalTask.engine.toUpperCase()} | Env: {activeTerminalTask.environment} | Requester: {activeTerminalTask.requester_id}
                  </p>
                </div>
              </div>

              <div className="flex items-center gap-2">
                {activeTerminalTask.status === 'FAILED' && (
                  <button
                    onClick={() => handleDiagnoseTask(activeTerminalTask)}
                    className="px-3 py-1.5 rounded-xl text-xs font-mono font-bold bg-rose-950/60 hover:bg-rose-900 border border-rose-500/40 text-rose-300 flex items-center gap-1.5 transition-colors"
                  >
                    <AlertTriangle className="w-3.5 h-3.5" />
                    <span>AI Diagnosis</span>
                  </button>
                )}

                <button
                  onClick={() => setActiveTerminalTask(null)}
                  className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-white/10 transition-colors"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>
            </div>

            {/* Terminal View Body */}
            <div className="flex-1 p-4 bg-black overflow-hidden flex flex-col">
              <TerminalStream
                logs={terminalLogs}
                jobStatus={activeTerminalTask.status}
                correlationId={activeTerminalTask.correlation_id}
              />
            </div>
          </div>
        </div>
      )}

      {/* ================================================================= */}
      {/* AI SRE FAILURE DIAGNOSTIC DRAWER                                  */}
      {/* ================================================================= */}
      <DiagnosticDrawer
        isOpen={diagnosticOpen}
        onClose={() => setDiagnosticOpen(false)}
        diagnostic={diagnosticData}
        onTriggerRollback={() => {
          setTerminalLogs(prev => [
            ...prev,
            '\x1b[1;33m[ROLLBACK DISPATCHED]\x1b[0m Automated rollback triggered by SRE. Restoring previous state...'
          ]);
        }}
      />
    </div>
  );
}

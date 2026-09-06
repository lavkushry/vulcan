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
  Sparkles,
  Server,
  FileSpreadsheet,
  Download,
  Users,
  Check,
  X,
  Radio
} from 'lucide-react';

import ChatAssistant, { ChatLaunchPayload } from '@/components/ChatAssistant';
import TaskMatrixTable, { TaskRecord } from '@/components/TaskMatrixTable';
import TerminalAuditWorkspace from '@/components/TerminalAuditWorkspace';
import { DEMO_USERS, api } from '@/lib/api';

const API_BASE = 'http://localhost:8000/api/v1';

type TabId = 'chat' | 'matrix' | 'terminal';

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
    status: 'PENDING_APPROVAL',
    risk_tier: 'HIGH',
    requester_id: 'eng.alice',
    approver_id: null,
    duration_sec: 48,
    created_at: new Date(Date.now() - 48000).toISOString(),
    servicenow_chg: 'CHG-98412',
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
    servicenow_chg: 'CHG-98410',
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
    approver_id: 'lead.bob',
    duration_sec: 76,
    created_at: new Date(Date.now() - 2500000).toISOString(),
    error_message: 'Fatal: Storage pool VG_DATA has insufficient free extents for +100GB.',
    diagnostic: 'Storage pool VG_DATA exhausted. Root cause: automated quota throttle reached.',
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
    approver_id: 'lead.bob',
    duration_sec: 95,
    created_at: new Date(Date.now() - 95000).toISOString(),
    parameters: { cluster_name: 'prod-useast1-eks-01', desired_capacity: 24 }
  }
];

export default function Home() {
  // Active Tab View State
  const [activeTab, setActiveTab] = useState<TabId>('matrix');
  const [currentUser, setCurrentUser] = useState<string>(DEMO_USERS[0].id);

  // Task & Telemetry Data
  const [tasks, setTasks] = useState<TaskRecord[]>(INITIAL_FALLBACK_TASKS);
  const [selectedTaskId, setSelectedTaskId] = useState<string | null>('EXEC-9821');
  const [isLoadingTasks, setIsLoadingTasks] = useState(false);

  const [telemetry, setTelemetry] = useState({
    catalogSize: 120,
    activeRunners: 2,
    lastAuditHash: '0x9a8f12c4e7b8',
    isAuditValid: true
  });

  // Fetch tasks and telemetry
  const loadData = useCallback(async () => {
    try {
      // 1. Load tasks from /api/v1/tasks or /api/v1/jobs
      const tasksRes = await fetch(`${API_BASE}/tasks?limit=100`);
      if (tasksRes.ok) {
        const data = await tasksRes.json();
        if (Array.isArray(data.tasks) && data.tasks.length > 0) {
          setTasks(data.tasks);
        }
      } else {
        // Fallback to /api/v1/jobs
        const jobsRes = await fetch(`${API_BASE}/jobs`);
        if (jobsRes.ok) {
          const rawJobs = await jobsRes.json();
          const jobList = Array.isArray(rawJobs) ? rawJobs : rawJobs.jobs;
          if (Array.isArray(jobList) && jobList.length > 0) {
            const mapped: TaskRecord[] = jobList.map((j: any) => ({
              id: j.id || j.job_id,
              correlation_id: j.correlation_id,
              identifier: j.identifier || j.playbook_identifier || 'playbook',
              name: j.name || j.playbook_name || 'Automation Task',
              engine: j.engine || 'ansible',
              category: j.category || 'general',
              target_resource: j.target_resource_id || j.target_resource || 'node-01',
              environment: j.environment || 'PROD',
              status: j.status,
              risk_tier: j.risk_tier || 'HIGH',
              requester_id: j.requester_id,
              approver_id: j.approver_id,
              duration_sec: 45,
              created_at: j.created_at || new Date().toISOString(),
              parameters: j.parameters || {},
              servicenow_chg: j.servicenow_chg,
              error_message: j.error_message,
              diagnostic: j.diagnostic
            }));
            setTasks(mapped);
          }
        }
      }

      // 2. Load health & telemetry
      const healthRes = await fetch(`${API_BASE}/health`);
      if (healthRes.ok) {
        const h = await healthRes.json();
        setTelemetry({
          catalogSize: h.catalog_size || 120,
          activeRunners: h.active_jobs_count || 2,
          lastAuditHash: h.audit_tip_hash ? `${h.audit_tip_hash.slice(0, 10)}...` : '0x9a8f12c4...',
          isAuditValid: h.audit_chain_valid ?? true
        });
      }
    } catch (err) {
      console.warn("Backend poll: keeping fallback cache active.");
    }
  }, []);

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 3000);
    return () => clearInterval(interval);
  }, [loadData]);

  // Handle Dispatch from Chat Assistant
  const handleDispatchTask = async (payload: ChatLaunchPayload) => {
    try {
      const res = await fetch(`${API_BASE}/tasks/dispatch`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Dispatch rejected by control plane.");
      }

      const newJob = await res.json();
      await loadData();

      // Automatically select this job and open the Terminal tab
      setSelectedTaskId(newJob.correlation_id || newJob.job_id);
      setActiveTab('terminal');

      return newJob;
    } catch (err) {
      console.error("Dispatch error:", err);
      throw err;
    }
  };

  // Handle Maker-Checker Approval
  const handleApproveTask = async (task: TaskRecord) => {
    try {
      await api.approveJob(task.id || task.correlation_id, currentUser);
      await loadData();
      setSelectedTaskId(task.correlation_id);
      setActiveTab('terminal');
    } catch (err: any) {
      alert(`Approval error: ${err.message}`);
    }
  };

  // Handle Maker-Checker Rejection
  const handleRejectTask = async (task: TaskRecord) => {
    try {
      await api.rejectJob(task.id || task.correlation_id, currentUser);
      await loadData();
    } catch (err: any) {
      alert(`Rejection error: ${err.message}`);
    }
  };

  // Navigation handlers
  const handleOpenTerminalForTask = (task: TaskRecord) => {
    setSelectedTaskId(task.correlation_id || task.id);
    setActiveTab('terminal');
  };

  // Counts for top tabs
  const pendingCount = tasks.filter(t => t.status === 'PENDING_APPROVAL').length;
  const runningCount = tasks.filter(t => t.status === 'RUNNING' || t.status === 'VERIFYING').length;

  return (
    <div className="flex flex-col h-screen bg-[#07090E] text-slate-100 font-sans select-none overflow-hidden">
      {/* ===================================================================== */}
      {/* TOP GLOBAL HEADER WITH TELEMETRY HUD & NAVIGATION TABS                 */}
      {/* ===================================================================== */}
      <header className="h-16 px-6 border-b border-slate-800/80 bg-[#0A0E16]/95 backdrop-blur-md flex items-center justify-between gap-4 z-20 shrink-0">
        {/* Brand & Platform Identity */}
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-cyan-500 to-blue-600 flex items-center justify-center text-black font-black text-sm shadow-md shadow-cyan-500/20">
            V
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-mono text-sm font-black tracking-widest text-cyan-400">
                PROJECT VULCAN
              </span>
              <span className="px-1.5 py-0.2 rounded text-[9px] font-mono font-bold bg-cyan-950/80 text-cyan-300 border border-cyan-500/30 uppercase">
                Enterprise OS
              </span>
            </div>
            <p className="text-[11px] text-slate-500 font-mono hidden sm:block">
              Banking Automation Control Plane · PNC Standard
            </p>
          </div>
        </div>

        {/* Center: Live Telemetry HUD */}
        <div className="hidden xl:flex items-center gap-6 px-4 py-1.5 rounded-2xl bg-[#07090E] border border-slate-800 text-xs font-mono">
          <div className="flex items-center gap-2">
            <Layers className="w-3.5 h-3.5 text-cyan-400" />
            <span className="text-slate-400">Catalog:</span>
            <span className="text-white font-bold">{telemetry.catalogSize} Modules</span>
          </div>

          <div className="flex items-center gap-2">
            <Activity className="w-3.5 h-3.5 text-emerald-400 animate-pulse" />
            <span className="text-slate-400">Runners:</span>
            <span className="text-emerald-400 font-bold">{telemetry.activeRunners} Active</span>
          </div>

          <div className="flex items-center gap-2">
            <ShieldCheck className="w-3.5 h-3.5 text-purple-400" />
            <span className="text-slate-400">Merkle Tip:</span>
            <span className="text-purple-300 font-mono">{telemetry.lastAuditHash}</span>
          </div>
        </div>

        {/* Top Navigation Tabs */}
        <nav className="flex items-center rounded-xl bg-[#07090E] border border-slate-800 p-1">
          {/* Tab 1: Chat & Launch Assistant */}
          <button
            onClick={() => setActiveTab('chat')}
            className={`px-3.5 py-1.5 rounded-lg text-xs font-medium flex items-center gap-2 transition-all ${
              activeTab === 'chat'
                ? 'bg-cyan-600/20 text-cyan-300 border border-cyan-500/40 shadow-sm font-semibold'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <Sparkles className="w-3.5 h-3.5 text-cyan-400" />
            <span>Chat Assistant</span>
          </button>

          {/* Tab 2: High-Filtered Task & Inventory Matrix */}
          <button
            onClick={() => setActiveTab('matrix')}
            className={`px-3.5 py-1.5 rounded-lg text-xs font-medium flex items-center gap-2 transition-all ${
              activeTab === 'matrix'
                ? 'bg-cyan-600/20 text-cyan-300 border border-cyan-500/40 shadow-sm font-semibold'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <FileSpreadsheet className="w-3.5 h-3.5 text-blue-400" />
            <span>Task Matrix</span>
            {pendingCount > 0 && (
              <span className="px-1.5 py-0.2 rounded-full text-[10px] font-mono font-bold bg-amber-500/20 text-amber-300 border border-amber-500/40">
                {pendingCount}
              </span>
            )}
          </button>

          {/* Tab 3: Live Terminal & Audit Log */}
          <button
            onClick={() => setActiveTab('terminal')}
            className={`px-3.5 py-1.5 rounded-lg text-xs font-medium flex items-center gap-2 transition-all ${
              activeTab === 'terminal'
                ? 'bg-cyan-600/20 text-cyan-300 border border-cyan-500/40 shadow-sm font-semibold'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <TerminalIcon className="w-3.5 h-3.5 text-emerald-400" />
            <span>Live Terminal</span>
            {runningCount > 0 && (
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
            )}
          </button>
        </nav>

        {/* Right: Persona Switcher (Alice / Bob) */}
        <div className="flex items-center gap-3">
          <label className="flex items-center gap-2 text-xs font-mono text-slate-400 bg-[#07090E] border border-slate-800 px-3 py-1.5 rounded-xl">
            <Users className="w-3.5 h-3.5 text-cyan-400" />
            <span className="hidden md:inline">acting as:</span>
            <select
              value={currentUser}
              onChange={(e) => setCurrentUser(e.target.value)}
              className="bg-transparent text-slate-200 font-semibold focus:outline-none cursor-pointer"
            >
              {DEMO_USERS.map((u) => (
                <option key={u.id} value={u.id} className="bg-[#0A0E16] text-white">
                  {u.label}
                </option>
              ))}
            </select>
          </label>
        </div>
      </header>

      {/* ===================================================================== */}
      {/* ACTIVE TAB CONTENT WORKSPACE                                          */}
      {/* ===================================================================== */}
      <div className="flex-1 overflow-hidden">
        {/* TAB 1: Chat & Launch Assistant */}
        {activeTab === 'chat' && (
          <div className="h-full p-4 max-w-5xl mx-auto flex flex-col overflow-hidden">
            <ChatAssistant
              currentUser={currentUser}
              onDispatchTask={handleDispatchTask}
              onSelectTaskToView={(corrId) => {
                setSelectedTaskId(corrId);
                setActiveTab('terminal');
              }}
            />
          </div>
        )}

        {/* TAB 2: High-Filtered Task & Inventory Matrix */}
        {activeTab === 'matrix' && (
          <TaskMatrixTable
            tasks={tasks}
            currentUser={currentUser}
            onOpenTerminal={handleOpenTerminalForTask}
            onApproveTask={handleApproveTask}
            onRejectTask={handleRejectTask}
            onRefresh={loadData}
            isLoading={isLoadingTasks}
          />
        )}

        {/* TAB 3: Dedicated Live Terminal & Audit Log */}
        {activeTab === 'terminal' && (
          <TerminalAuditWorkspace
            tasks={tasks}
            selectedTaskId={selectedTaskId}
            currentUser={currentUser}
            onSelectTask={setSelectedTaskId}
            onApproveTask={handleApproveTask}
            onRejectTask={handleRejectTask}
            auditChainTip={telemetry.lastAuditHash}
          />
        )}
      </div>
    </div>
  );
}

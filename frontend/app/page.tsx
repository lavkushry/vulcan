'use client';

import React, { useState, useEffect } from 'react';
import { 
  Activity, 
  Terminal as TerminalIcon, 
  Cpu, 
  ShieldCheck, 
  Search, 
  RotateCcw, 
  Play, 
  CheckCircle2, 
  AlertTriangle 
} from 'lucide-react';

import AdaptiveBentoCanvas from '../components/AdaptiveBentoCanvas';
import MakerCheckerDeck from '../components/MakerCheckerDeck';
import TerminalStream from '../components/TerminalStream';
import DiagnosticDrawer from '../components/DiagnosticDrawer';
import UniversalCommandPalette from '../components/UniversalCommandPalette';

export default function MissionControlDashboard() {
  const [activeJob, setActiveJob] = useState<any>(null);
  const [logs, setLogs] = useState<string[]>([]);
  const [isExecuting, setIsExecuting] = useState(false);
  const [isApproving, setIsApproving] = useState(false);
  const [diagnosticOpen, setDiagnosticOpen] = useState(false);
  const [diagnosticData, setDiagnosticData] = useState<any>(null);
  const [commandPaletteOpen, setCommandPaletteOpen] = useState(false);

  // Initial Telemetry Stats
  const [stats, setStats] = useState({
    activeRunners: 3,
    peakCapacity: 75,
    merkleChainValid: true,
    lastAuditHash: 'a7b3...c91e',
    queueDwellSec: 0.12,
  });

  const handleLaunchJob = async (jobPayload: any) => {
    setIsExecuting(true);
    setLogs([]);

    // Create Synthetic / Real Job State
    const correlationId = `EXEC-${Math.floor(1000 + Math.random() * 9000)}`;
    const newJob = {
      id: `job-${Date.now()}`,
      correlation_id: correlationId,
      playbook_identifier: jobPayload.catalog_identifier,
      playbook_name: 'F5 BIG-IP SSL Certificate Renewal',
      requester_id: jobPayload.requester_id,
      target_resource_id: jobPayload.target_resource_id,
      parameters: jobPayload.parameters,
      servicenow_chg: jobPayload.servicenow_chg,
      risk_tier: 'HIGH',
      status: 'PENDING_APPROVAL',
      created_at: new Date().toISOString(),
    };

    setActiveJob(newJob);
    setIsExecuting(false);
  };

  const handleApprove = async (decision: string, reason: string) => {
    if (!activeJob) return;
    setIsApproving(true);

    // Simulate Server Action / REST API response
    setTimeout(() => {
      if (decision === 'APPROVE') {
        const approvedJob = { ...activeJob, status: 'RUNNING', approver_id: 'lead.bob' };
        setActiveJob(approvedJob);
        setIsApproving(false);
        streamExecutionLogs(approvedJob.correlation_id);
      } else {
        setActiveJob({ ...activeJob, status: 'REJECTED' });
        setIsApproving(false);
      }
    }, 600);
  };

  const streamExecutionLogs = (corrId: string) => {
    const rawSteps = [
      '\x1b[1;36m[PROJECT VULCAN RUNNER]\x1b[0m Initializing runtime sandbox for net-f5-cert-renew...',
      '\x1b[34m[PAM]\x1b[0m Ephemeral SSH credentials bound to f5-edge-01.pnc.com in /dev/shm.',
      '\x1b[32m[AUDIT]\x1b[0m Synchronous pre-run commit registered to Merkle hash ledger.',
      'PLAY [Renew SSL/TLS Certificate on F5 BIG-IP VIP] *****************************',
      'TASK [Gathering Facts] *********************************************************',
      'ok: [f5-edge-01.pnc.com]',
      'TASK [f5_vip_update : Validate existing SSL Certificate Expiration] ************',
      'ok: [f5-edge-01.pnc.com] => {"cert_cn": "f5-edge-01.pnc.com", "status": "EXPIRING_SOON"}',
      'TASK [f5_vip_update : Generate 4096-bit RSA Private Key and CSR] **************',
      'changed: [f5-edge-01.pnc.com] => {"algorithm": "RSA-4096", "key_generated": true}',
      'TASK [f5_vip_update : Submit CSR to PNC Internal Automated CA] *****************',
      'ok: [f5-edge-01.pnc.com] => {"ca_response": "ISSUED", "valid_days": 90}',
      'TASK [f5_vip_update : Bind New TLS Certificate to SSL Client Profile] **********',
      'changed: [f5-edge-01.pnc.com] => {"profile": "clientssl-pnc-prod", "vip": "10.200.1.50"}',
      'TASK [f5_vip_update : Synchronize Configuration Across Active/Standby Pair] ****',
      'changed: [f5-edge-01.pnc.com] => {"sync_status": "IN_SYNC", "peer": "f5-secondary-01"}',
      'PLAY RECAP *********************************************************************',
      'f5-edge-01.pnc.com         : ok=6    changed=3    unreachable=0    failed=0',
      '\x1b[32m[HEALTH]\x1b[0m Synthetic probe passed: TLS 1.3 negotiated, HTTP 200 OK, latency=24ms.',
      '\x1b[1;32m[SUCCESS]\x1b[0m Execution verified healthy. ServiceNow CHG0098412 marked Closed Complete.'
    ];

    let current = 0;
    const interval = setInterval(() => {
      if (current < rawSteps.length) {
        setLogs((prev) => [...prev, rawSteps[current]]);
        current++;
      } else {
        clearInterval(interval);
        setActiveJob((prev: any) => ({ ...prev, status: 'SUCCESS', exit_code: 0 }));
      }
    }, 150);
  };

  const handleSimulateFailure = () => {
    const failureLog = [
      '\x1b[1;36m[PROJECT VULCAN RUNNER]\x1b[0m Initializing runtime sandbox for net-f5-cert-renew...',
      'TASK [f5_vip_update : Bind SSL Cert] *********************',
      'FATAL: [f5-edge-01.pnc.com]: FAILED! => {"msg": "Connection refused on port 443 / SSL handshake failure"}',
      '\x1b[1;31m[DEGRADED]\x1b[0m Health check probe failed: latency=950ms error_rate=45%'
    ];
    setLogs(failureLog);
    setActiveJob((prev: any) => ({ ...prev, status: 'FAILED', exit_code: 1 }));
    setDiagnosticData({
      fault_summary: 'F5 VIP SSL Handshake / Port 443 Connection Refused',
      root_cause: 'The target F5 load balancer profile failed TLS negotiation on port 443 during client-ssl handshake.',
      blast_radius: 'Inbound HTTPS customer traffic to the VIP may experience connection resets if uncommitted profile was active.',
      recommended_action: 'Execute automated rollback playbook to restore previous valid SSL profile and re-verify upstream health.',
      windowed_log: failureLog.join('\n'),
      diagnosis_latency_ms: 280.0
    });
    setDiagnosticOpen(true);
  };

  return (
    <div className="space-y-6">
      {/* Telemetry HUD Bar */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        <div className="glass-panel p-3 rounded-lg flex items-center gap-3">
          <Activity className="w-5 h-5 text-cyan-400" />
          <div>
            <div className="text-[10px] uppercase font-mono text-slate-400">Concurrent Runners</div>
            <div className="text-sm font-bold text-white font-mono">{stats.activeRunners} / {stats.peakCapacity}</div>
          </div>
        </div>

        <div className="glass-panel p-3 rounded-lg flex items-center gap-3">
          <Cpu className="w-5 h-5 text-purple-400" />
          <div>
            <div className="text-[10px] uppercase font-mono text-slate-400">Little's Law Arrival</div>
            <div className="text-sm font-bold text-purple-300 font-mono">0.125 jobs/s</div>
          </div>
        </div>

        <div className="glass-panel p-3 rounded-lg flex items-center gap-3">
          <ShieldCheck className="w-5 h-5 text-emerald-400" />
          <div>
            <div className="text-[10px] uppercase font-mono text-slate-400">Merkle Chain</div>
            <div className="text-sm font-bold text-emerald-400 font-mono">VALIDATED</div>
          </div>
        </div>

        <div className="glass-panel p-3 rounded-lg flex items-center gap-3">
          <TerminalIcon className="w-5 h-5 text-amber-400" />
          <div>
            <div className="text-[10px] uppercase font-mono text-slate-400">Queue Dwell Time</div>
            <div className="text-sm font-bold text-amber-300 font-mono">&lt; 150ms</div>
          </div>
        </div>

        <button
          onClick={() => setCommandPaletteOpen(true)}
          className="glass-panel p-3 rounded-lg flex items-center justify-between text-left hover:border-cyan-500/40 transition-colors group"
        >
          <div className="flex items-center gap-2">
            <Search className="w-4 h-4 text-cyan-400 group-hover:scale-110 transition-transform" />
            <span className="text-xs font-mono text-slate-300">Cmd + K</span>
          </div>
          <span className="text-[10px] font-mono text-cyan-400 px-1.5 py-0.5 rounded bg-cyan-950/60 border border-cyan-500/30">
            PLAYBOOKS
          </span>
        </button>
      </div>

      {/* Bento Grid: Adaptive Slot-Filling Canvas */}
      <div className="glass-panel rounded-xl p-5 border border-glass-border">
        <AdaptiveBentoCanvas onExecute={handleLaunchJob} isExecuting={isExecuting} />
      </div>

      {/* Maker-Checker Approval Deck (if job is pending approval) */}
      {activeJob && activeJob.status === 'PENDING_APPROVAL' && (
        <MakerCheckerDeck
          job={activeJob}
          currentUserId="lead.bob"
          onApprove={handleApprove}
          isProcessing={isApproving}
        />
      )}

      {/* Live 60 FPS WebGL Terminal Stream & Controls */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <h3 className="text-xs font-mono font-bold uppercase tracking-wider text-slate-300 flex items-center gap-2">
            <TerminalIcon className="w-4 h-4 text-cyan-400" />
            Real-Time Telemetry &amp; Execution Output
          </h3>

          <div className="flex items-center gap-2">
            <button
              onClick={handleSimulateFailure}
              className="px-3 py-1 rounded bg-rose-950/40 hover:bg-rose-900 border border-rose-500/30 text-rose-300 text-[11px] font-mono font-bold flex items-center gap-1.5 transition-colors"
            >
              <AlertTriangle className="w-3.5 h-3.5" />
              Simulate Failure &amp; AI Diagnosis
            </button>
          </div>
        </div>

        <TerminalStream
          logs={logs}
          jobStatus={activeJob?.status || 'IDLE'}
          correlationId={activeJob?.correlation_id || ''}
        />
      </div>

      {/* Slide-out AI SRE Failure Diagnostic Drawer */}
      <DiagnosticDrawer
        isOpen={diagnosticOpen}
        onClose={() => setDiagnosticOpen(false)}
        diagnostic={diagnosticData}
        onTriggerRollback={() => {
          setLogs((prev) => [...prev, '\x1b[1;33m[ROLLBACK DISPATCHED]\x1b[0m Automated rollback triggered by SRE. Restoring previous state...']);
        }}
      />

      {/* Universal Command Palette (Cmd + K) */}
      <UniversalCommandPalette
        isOpen={commandPaletteOpen}
        onClose={() => setCommandPaletteOpen(false)}
        onSelectPlaybook={(item) => {
          handleLaunchJob({
            catalog_identifier: item.identifier,
            target_resource_id: 'f5-edge-01.pnc.com',
            requester_id: 'engineer.alice',
            parameters: { hostname: 'f5-edge-01.pnc.com', vip_ip: '10.200.1.50', cert_valid_days: 90 },
            servicenow_chg: 'CHG0098412'
          });
        }}
      />
    </div>
  );
}

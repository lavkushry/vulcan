'use client';

import React, { useState } from 'react';
import { Database, ShieldCheck, CheckCircle2, Clock, Terminal, AlertTriangle } from 'lucide-react';

interface BentoCanvasProps {
  onExecute: (params: any) => void;
  isExecuting?: boolean;
}

export default function AdaptiveBentoCanvas({ onExecute, isExecuting = false }: BentoCanvasProps) {
  const [selectedEnv, setSelectedEnv] = useState<'DEV' | 'UAT' | 'PROD'>('PROD');
  const [targetHost, setTargetHost] = useState('f5-edge-01.pnc.com');
  const [vipIp, setVipIp] = useState('10.200.1.50');
  const [validDays, setValidDays] = useState(90);
  const [snowTicket, setSnowTicket] = useState('CHG0098412');
  const [cmdbStatus, setCmdbStatus] = useState('VERIFIED');

  const handleLaunch = () => {
    onExecute({
      catalog_identifier: 'net-f5-cert-renew',
      target_resource_id: targetHost,
      requester_id: 'engineer.alice',
      parameters: {
        hostname: targetHost,
        vip_ip: vipIp,
        cert_valid_days: validDays
      },
      servicenow_chg: snowTicket
    });
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between pb-2 border-b border-glass-border">
        <div>
          <h2 className="text-sm font-semibold tracking-wide text-white uppercase flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-cyan-400"></span>
            Adaptive Bento Execution Canvas
          </h2>
          <p className="text-xs text-slate-400">Slot-Filling Parameter Matrix for F5 SSL Renewal</p>
        </div>
        <div className="text-xs font-mono text-cyan-400 bg-cyan-950/40 px-2 py-1 rounded border border-cyan-500/20">
          SCHEMA: net.f5.renew_certificate:a1b2c3d
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* Card 1: Target Environment Pill Selector */}
        <div className="glass-card rounded-lg p-4 space-y-3">
          <div className="flex items-center justify-between text-xs text-slate-400">
            <span className="font-semibold uppercase text-slate-300">[1] Deployment Tier</span>
            <ShieldCheck className="w-4 h-4 text-cyan-400" />
          </div>
          <div className="grid grid-cols-3 gap-2">
            {(['DEV', 'UAT', 'PROD'] as const).map((env) => (
              <button
                key={env}
                type="button"
                onClick={() => setSelectedEnv(env)}
                className={`py-2 px-3 rounded text-xs font-mono font-bold transition-all ${
                  selectedEnv === env
                    ? env === 'PROD'
                      ? 'bg-amber-500/20 text-amber-300 border border-amber-500/50 shadow-glow-amber'
                      : 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/50 shadow-glow-cyan'
                    : 'bg-glass-raised text-slate-400 border border-glass-border hover:border-slate-500'
                }`}
              >
                [{env}]
              </button>
            ))}
          </div>
          <p className="text-[11px] text-slate-500">
            {selectedEnv === 'PROD'
              ? '★ High-Risk tier: Requires Maker-Checker approval and ServiceNow CHG.'
              : 'Low-Risk tier: Standard fast-path dispatch enabled.'}
          </p>
        </div>

        {/* Card 2: Host & VIP Target Spec */}
        <div className="glass-card rounded-lg p-4 space-y-3">
          <div className="flex items-center justify-between text-xs text-slate-400">
            <span className="font-semibold uppercase text-slate-300">[2] Target Host & VIP</span>
            <Database className="w-4 h-4 text-purple-400" />
          </div>
          <div className="space-y-2">
            <div>
              <label className="text-[10px] uppercase font-mono text-slate-400">FQDN Hostname</label>
              <input
                type="text"
                value={targetHost}
                onChange={(e) => setTargetHost(e.target.value)}
                className="w-full bg-glass-raised border border-glass-border rounded px-2.5 py-1 text-xs font-mono text-cyan-300 focus:outline-none focus:border-cyan-400"
              />
            </div>
            <div>
              <label className="text-[10px] uppercase font-mono text-slate-400">Virtual IP (VIP)</label>
              <input
                type="text"
                value={vipIp}
                onChange={(e) => setVipIp(e.target.value)}
                className="w-full bg-glass-raised border border-glass-border rounded px-2.5 py-1 text-xs font-mono text-cyan-300 focus:outline-none focus:border-cyan-400"
              />
            </div>
          </div>
        </div>

        {/* Card 3: ServiceNow Ticket & Maintenance Window */}
        <div className="glass-card rounded-lg p-4 space-y-3">
          <div className="flex items-center justify-between text-xs text-slate-400">
            <span className="font-semibold uppercase text-slate-300">[3] ServiceNow CHG Window</span>
            <CheckCircle2 className="w-4 h-4 text-emerald-400" />
          </div>
          <div>
            <label className="text-[10px] uppercase font-mono text-slate-400">CHG Number</label>
            <input
              type="text"
              value={snowTicket}
              onChange={(e) => setSnowTicket(e.target.value)}
              className="w-full bg-glass-raised border border-glass-border rounded px-2.5 py-1 text-xs font-mono text-emerald-400 focus:outline-none focus:border-emerald-400"
            />
          </div>
          <div className="bg-emerald-950/30 border border-emerald-500/20 rounded p-2 text-[11px] font-mono text-emerald-300 flex items-center justify-between">
            <span className="flex items-center gap-1.5">
              <Clock className="w-3.5 h-3.5 text-emerald-400" />
              Window: 00:00 - 23:59 UTC
            </span>
            <span className="font-bold">ACTIVE</span>
          </div>
        </div>
      </div>

      {/* Action Footer */}
      <div className="flex items-center justify-between pt-2">
        <div className="flex items-center gap-2 text-xs font-mono text-slate-400">
          <span className="w-2 h-2 rounded-full bg-emerald-400"></span>
          Parameters validated against Pydantic AST grammar.
        </div>
        <button
          onClick={handleLaunch}
          disabled={isExecuting}
          className="px-6 py-2.5 rounded-lg bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-400 hover:to-blue-500 text-white font-mono text-xs font-bold shadow-glow-cyan transition-all disabled:opacity-50 flex items-center gap-2"
        >
          <Terminal className="w-4 h-4" />
          {isExecuting ? 'DISPATCHING ORCHESTRATION...' : 'DISPATCH PLAYBOOK RUN [CMD+ENTER]'}
        </button>
      </div>
    </div>
  );
}

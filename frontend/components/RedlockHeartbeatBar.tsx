'use client';

import React, { useEffect, useState } from 'react';
import { AlertTriangle, ShieldAlert } from 'lucide-react';

interface RedlockProps {
  leaseTtlSeconds?: number; // default 30s
  watchdogIntervalSeconds?: number; // default 10s
  fencingToken?: number; // e.g. 10482
  targetResource?: string;
  quorumActive?: number; // e.g. 4
  quorumTotal?: number; // e.g. 5
  isHolding?: boolean;
  serverTtlMs?: number; // Telemetry from server WebSocket
  lastHeartbeatReceivedAt?: number; // Date.now() timestamp of last received heartbeat
}

export const RedlockHeartbeatBar: React.FC<RedlockProps> = ({
  leaseTtlSeconds = 30,
  watchdogIntervalSeconds = 10,
  fencingToken = 0,
  targetResource = 'unknown',
  quorumActive = 0,
  quorumTotal = 0,
  isHolding = false,
  serverTtlMs,
  lastHeartbeatReceivedAt,
}) => {
  const initialTtl = serverTtlMs ? serverTtlMs / 1000 : leaseTtlSeconds;
  const [remainingTtl, setRemainingTtl] = useState<number>(initialTtl);
  const [pulse, setPulse] = useState<boolean>(false);
  const [lastHeartbeat, setLastHeartbeat] = useState<number>(lastHeartbeatReceivedAt || Date.now());

  // Trigger pulse whenever a genuine server heartbeat arrives
  useEffect(() => {
    if (serverTtlMs !== undefined) {
      setRemainingTtl(serverTtlMs / 1000);
      setPulse(true);
      setLastHeartbeat(Date.now());
      const pulseTimer = setTimeout(() => setPulse(false), 800);
      return () => clearTimeout(pulseTimer);
    }
  }, [serverTtlMs, lastHeartbeatReceivedAt]);

  // Honest countdown: TTL strictly decreases toward 0 unless a real server heartbeat arrives
  useEffect(() => {
    if (!isHolding) return;
    const interval = setInterval(() => {
      setRemainingTtl((prev) => Math.max(0, +(prev - 0.1).toFixed(1)));
    }, 100);
    return () => clearInterval(interval);
  }, [isHolding]);

  const timeSinceLastHeartbeat = (Date.now() - lastHeartbeat) / 1000;
  const isSplitBrain = timeSinceLastHeartbeat > 10 && remainingTtl <= 0.5;
  const isHeartbeatLate = !isSplitBrain && timeSinceLastHeartbeat > (watchdogIntervalSeconds + 2);

  const percent = Math.max(0, Math.min(100, (remainingTtl / leaseTtlSeconds) * 100));
  const isCritical = remainingTtl < 5 || isSplitBrain;
  const isWarning = (remainingTtl < 10 && !isCritical) || isHeartbeatLate;

  return (
    <div className="flex flex-col gap-1.5 p-3 rounded-lg border border-slate-800 bg-[#0C101A] font-mono text-xs">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span
            className={`w-2 h-2 rounded-full ${
              pulse
                ? 'bg-emerald-400 scale-125 shadow-[0_0_8px_#00FF9D]'
                : isSplitBrain
                ? 'bg-rose-500 animate-ping'
                : isHeartbeatLate
                ? 'bg-amber-400 animate-pulse'
                : 'bg-cyan-400'
            } transition-all duration-300`}
          />
          <span className="font-semibold text-slate-200">
            Redlock Mutex: <code className="text-cyan-300">{targetResource}</code>
          </span>
          <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-800 text-slate-400 border border-slate-700">
            Fencing #{fencingToken}
          </span>
        </div>
        <div className="flex items-center gap-1.5 text-[11px] text-slate-400">
          <span>Multi-AZ Quorum:</span>
          <span className="text-emerald-400 font-bold">
            {quorumActive}/{quorumTotal} Nodes
          </span>
          <span className="flex items-center gap-0.5">
            {[...Array(quorumTotal)].map((_, i) => (
              <span
                key={i}
                className={`inline-block w-1.5 h-1.5 rounded-full ${
                  i < quorumActive ? 'bg-emerald-400' : 'bg-slate-600'
                }`}
              />
            ))}
          </span>
        </div>
      </div>

      {/* Countdown Progress Bar */}
      <div className="relative w-full h-1.5 rounded-full bg-slate-900 overflow-hidden border border-slate-800">
        <div
          style={{ width: `${percent}%` }}
          className={`h-full transition-all duration-100 ${
            isCritical
              ? 'bg-rose-500 shadow-[0_0_8px_#FF0055]'
              : isWarning
              ? 'bg-amber-400 shadow-[0_0_8px_#FFB800]'
              : 'bg-gradient-to-r from-cyan-500 to-emerald-400'
          }`}
        />
      </div>

      {/* Split-Brain Alarm Banner */}
      {isSplitBrain && (
        <div className="p-1.5 rounded bg-rose-950/40 border border-rose-500/60 text-rose-300 text-[10px] flex items-center gap-1.5 animate-pulse">
          <AlertTriangle className="w-3.5 h-3.5 text-rose-400 flex-shrink-0" />
          <span className="font-bold">
            SPLIT-BRAIN RISK: Heartbeat missed by daemon ({timeSinceLastHeartbeat.toFixed(0)}s &gt; 10s). Lock lease expiration imminent!
          </span>
        </div>
      )}

      {/* Delayed Heartbeat Warning Banner */}
      {isHeartbeatLate && !isSplitBrain && (
        <div className="p-1.5 rounded bg-amber-950/40 border border-amber-500/40 text-amber-300 text-[10px] flex items-center gap-1.5">
          <AlertTriangle className="w-3.5 h-3.5 text-amber-400 flex-shrink-0" />
          <span>
            Heartbeat delayed ({timeSinceLastHeartbeat.toFixed(1)}s elapsed). Awaiting watchdog renewal.
          </span>
        </div>
      )}

      <div className="flex items-center justify-between text-[10px] text-slate-400">
        <span className="flex items-center gap-1">
          <span>Watchdog Heartbeat (Telemetry-bound)</span>
          {pulse && (
            <span className="text-emerald-300 font-bold animate-pulse">
              • [PEXPIRE 30000 OK]
            </span>
          )}
        </span>
        <span
          className={
            isCritical
              ? 'text-rose-400 font-bold'
              : isWarning
              ? 'text-amber-400'
              : 'text-cyan-400'
          }
        >
          Lease: {remainingTtl.toFixed(1)}s / {leaseTtlSeconds}s
        </span>
      </div>
    </div>
  );
};

export default RedlockHeartbeatBar;

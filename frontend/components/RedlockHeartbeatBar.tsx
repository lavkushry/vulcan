'use client';

import React, { useEffect, useState } from 'react';

interface RedlockProps {
  leaseTtlSeconds?: number; // default 30s
  watchdogIntervalSeconds?: number; // default 10s
  fencingToken?: number; // e.g. 10482
  targetResource?: string;
  quorumActive?: number; // e.g. 4
  quorumTotal?: number; // e.g. 5
  isHolding?: boolean;
}

export const RedlockHeartbeatBar: React.FC<RedlockProps> = ({
  leaseTtlSeconds = 30,
  watchdogIntervalSeconds = 10,
  fencingToken = 10482,
  targetResource = 'prod-edge-vip',
  quorumActive = 4,
  quorumTotal = 5,
  isHolding = true,
}) => {
  const [remainingTtl, setRemainingTtl] = useState<number>(leaseTtlSeconds);
  const [pulse, setPulse] = useState<boolean>(false);

  useEffect(() => {
    if (!isHolding) return;
    const interval = setInterval(() => {
      setRemainingTtl((prev) => {
        if (prev <= 0.2) return leaseTtlSeconds;
        return +(prev - 0.1).toFixed(1);
      });
    }, 100);
    return () => clearInterval(interval);
  }, [isHolding, leaseTtlSeconds]);

  // Simulate Watchdog 10s renewal pulse
  useEffect(() => {
    if (!isHolding) return;
    const watchdogTimer = setInterval(() => {
      setRemainingTtl(leaseTtlSeconds);
      setPulse(true);
      setTimeout(() => setPulse(false), 900);
    }, watchdogIntervalSeconds * 1000);
    return () => clearInterval(watchdogTimer);
  }, [isHolding, leaseTtlSeconds, watchdogIntervalSeconds]);

  const percent = Math.max(0, Math.min(100, (remainingTtl / leaseTtlSeconds) * 100));
  const isWarning = remainingTtl < 10;
  const isCritical = remainingTtl < 5;

  return (
    <div className="flex flex-col gap-1.5 p-3 rounded-lg border border-slate-800 bg-[#0C101A] font-mono text-xs">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span
            className={`w-2 h-2 rounded-full ${
              pulse
                ? 'bg-emerald-400 scale-125 shadow-[0_0_8px_#00FF9D]'
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

      <div className="flex items-center justify-between text-[10px] text-slate-400">
        <span className="flex items-center gap-1">
          <span>Watchdog Heartbeat (10s daemon renewal)</span>
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

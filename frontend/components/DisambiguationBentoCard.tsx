'use client';

import React from 'react';
import { HelpCircle, ArrowRight, ShieldAlert, CheckCircle2, Shield, Zap } from 'lucide-react';

export interface DisambiguationCandidate {
  identifier: string;
  name: string;
  engine: string;
  cosineSimilarity: number;
  blastRadius: 'HIGH' | 'MEDIUM' | 'LOW';
  governanceGate: 'MAKER_CHECKER' | 'PRE_APPROVED';
  summary: string;
  shortcut: string;
}

export interface DisambiguationBentoCardProps {
  originalQuery: string;
  deltaSim: number;
  candidates: DisambiguationCandidate[];
  onSelect: (identifier: string) => void;
}

export const DisambiguationBentoCard: React.FC<DisambiguationBentoCardProps> = ({
  originalQuery,
  deltaSim,
  candidates,
  onSelect,
}) => {
  return (
    <div className="rounded-xl border border-amber-500/30 bg-[#0C101A] p-4 flex flex-col gap-3 font-mono text-xs shadow-xl" role="region" aria-label="Action disambiguation choice">
      <div className="flex items-center justify-between border-b border-slate-800 pb-2.5">
        <div className="flex items-center gap-2">
          <HelpCircle size={16} className="text-amber-400" />
          <span className="font-bold text-sm text-slate-100 font-sans">
            Which action did you mean?
          </span>
        </div>
        <span className="text-[10px] px-2 py-0.5 rounded bg-amber-950/40 text-amber-300 border border-amber-500/30">
          Multiple Matches Found
        </span>
      </div>

      <p className="text-slate-300 font-sans text-xs">
        Your request <strong className="text-cyan-300 font-mono">&ldquo;{originalQuery}&rdquo;</strong> matches multiple actions in the catalog. Choose the one that matches your goal:
      </p>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3 pt-1">
        {candidates.map((cand) => {
          const isHighBlast = cand.blastRadius === 'HIGH';
          return (
            <button
              key={cand.identifier}
              type="button"
              onClick={() => onSelect(cand.identifier)}
              aria-label={`Select ${cand.name}`}
              className="group text-left rounded-xl bg-[#07090E] border border-slate-800 hover:border-cyan-500/60 p-4 flex flex-col justify-between gap-3 transition-all hover:bg-slate-900/50 hover:shadow-[0_0_15px_rgba(0,240,255,0.15)] focus:outline-none focus:ring-2 focus:ring-cyan-400"
            >
              <div className="flex flex-col gap-1.5 w-full">
                <div className="flex items-center justify-between">
                  <span className="text-[10px] px-2 py-0.5 rounded bg-slate-800 text-slate-300 border border-slate-700 font-mono uppercase">
                    {cand.engine}
                  </span>
                  <span className="text-[10px] text-cyan-400 font-mono">
                    Match: {(cand.cosineSimilarity * 100).toFixed(0)}%
                  </span>
                </div>

                <h4 className="font-bold text-sm text-slate-100 group-hover:text-cyan-300 transition-colors font-sans">
                  {cand.name}
                </h4>
                <p className="text-xs text-slate-400 leading-relaxed font-sans">
                  {cand.summary}
                </p>
              </div>

              <div className="flex flex-col gap-2 pt-2 border-t border-slate-800/80 text-[11px] w-full font-mono">
                <div className="flex items-center justify-between">
                  <span className="text-slate-500">Expected Impact:</span>
                  <span className={`font-semibold flex items-center gap-1 ${
                    isHighBlast ? 'text-rose-400' : 'text-emerald-400'
                  }`}>
                    {isHighBlast ? <ShieldAlert size={12} /> : <CheckCircle2 size={12} />}
                    {cand.blastRadius}
                  </span>
                </div>

                <div className="flex items-center justify-between">
                  <span className="text-slate-500">Governance:</span>
                  <span className="text-slate-300">
                    {cand.governanceGate === 'MAKER_CHECKER' ? 'Requires Approval' : 'Pre-approved'}
                  </span>
                </div>

                <div className="mt-1 w-full py-2 rounded-lg bg-slate-800/80 group-hover:bg-cyan-500 group-hover:text-slate-950 text-slate-200 font-bold text-xs flex items-center justify-center gap-1.5 transition-all">
                  <span>Select this action</span>
                  <ArrowRight size={13} />
                </div>
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
};

export default DisambiguationBentoCard;

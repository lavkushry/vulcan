'use client';

import React from 'react';
import { AlertCircle, ArrowRight, ShieldAlert, CheckCircle2 } from 'lucide-react';

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
    <div className="rounded-xl border border-amber-500/30 bg-[#0C101A] p-4 flex flex-col gap-3 font-mono text-xs shadow-xl">
      <div className="flex items-center justify-between border-b border-slate-800 pb-2">
        <div className="flex items-center gap-2">
          <AlertCircle size={15} className="text-amber-400" />
          <span className="font-bold text-slate-200 uppercase tracking-wider">
            Semantic Ambivalence Detected (Δsim = {deltaSim.toFixed(3)} &lt; 0.05)
          </span>
        </div>
        <span className="text-[10px] px-2 py-0.5 rounded bg-amber-950/40 text-amber-300 border border-amber-500/30">
          Zero-Autonomous-Guess Guard
        </span>
      </div>

      <p className="text-slate-400 text-xs">
        Your prompt <code className="text-cyan-300">&ldquo;{originalQuery}&rdquo;</code> matches two adjacent enterprise catalog centroids. Please disambiguate your operational intent:
      </p>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3 pt-1">
        {candidates.map((cand, idx) => {
          const isHighBlast = cand.blastRadius === 'HIGH';
          return (
            <div
              key={cand.identifier}
              onClick={() => onSelect(cand.identifier)}
              className="group cursor-pointer rounded-lg bg-[#07090E] border border-slate-800 hover:border-cyan-500/60 p-3.5 flex flex-col justify-between gap-3 transition-all hover:shadow-[0_0_15px_rgba(0,240,255,0.15)]"
            >
              <div className="flex flex-col gap-1.5">
                <div className="flex items-center justify-between">
                  <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-800 text-slate-300 border border-slate-700">
                    {cand.engine.toUpperCase()}
                  </span>
                  <span className="text-[10px] text-cyan-400 font-bold">
                    Sim: {(cand.cosineSimilarity * 100).toFixed(1)}%
                  </span>
                </div>

                <h4 className="font-bold text-slate-100 group-hover:text-cyan-300 transition-colors">
                  {cand.name}
                </h4>
                <p className="text-[11px] text-slate-400 leading-relaxed">
                  {cand.summary}
                </p>
              </div>

              <div className="flex flex-col gap-2 pt-2 border-t border-slate-800/80 text-[10px]">
                <div className="flex items-center justify-between">
                  <span className="text-slate-500">Blast Radius:</span>
                  <span className={`font-bold flex items-center gap-1 ${
                    isHighBlast ? 'text-rose-400' : 'text-emerald-400'
                  }`}>
                    {isHighBlast ? <ShieldAlert size={11} /> : <CheckCircle2 size={11} />}
                    {cand.blastRadius}
                  </span>
                </div>

                <div className="flex items-center justify-between">
                  <span className="text-slate-500">Governance Gate:</span>
                  <span className="text-slate-300">
                    {cand.governanceGate === 'MAKER_CHECKER' ? 'Maker-Checker (Dual Signoff)' : 'Pre-approved'}
                  </span>
                </div>

                <button
                  type="button"
                  className="mt-1 w-full py-1.5 rounded bg-slate-800 group-hover:bg-cyan-500 text-slate-300 group-hover:text-slate-950 font-bold text-[11px] flex items-center justify-center gap-1 transition-all"
                >
                  <span>Select Intent ({cand.shortcut})</span>
                  <ArrowRight size={11} />
                </button>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default DisambiguationBentoCard;

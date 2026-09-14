import Link from 'next/link';
import { Compass, ArrowRight } from 'lucide-react';

export default function NotFound() {
  return (
    <div className="min-h-screen bg-canvas-void text-slate-200 flex items-center justify-center p-6 font-mono">
      <div className="max-w-md w-full bg-slate-900/80 border border-glass-border rounded-xl p-6 shadow-2xl backdrop-blur-md space-y-4 text-center">
        <div className="inline-flex p-3 rounded-xl bg-cyan-500/10 border border-cyan-500/30 text-cyan-400">
          <Compass size={28} />
        </div>
        <h1 className="text-base font-bold text-white uppercase tracking-wider">Page Not Found</h1>
        <p className="text-xs text-slate-400 font-sans leading-relaxed">
          The requested path could not be located in the Vulcan Control Plane console.
        </p>
        <div className="pt-2 flex justify-center">
          <Link
            href="/chat"
            className="px-4 py-2 rounded-lg bg-cyan-600 hover:bg-cyan-500 text-white font-mono text-xs font-semibold flex items-center gap-2 transition-all cursor-pointer"
          >
            <span>Return to Chat</span>
            <ArrowRight size={14} />
          </Link>
        </div>
      </div>
    </div>
  );
}

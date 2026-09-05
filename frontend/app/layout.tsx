import React from 'react';
import './globals.css';

export const metadata = {
  title: 'Project Vulcan | Enterprise Automation Control Plane',
  description: 'Mission-critical banking automation OS (PNC Bank Standard)',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className="bg-canvas-void text-slate-200 min-h-screen flex flex-col font-sans selection:bg-cyan-500/30 selection:text-cyan-200">
        {/* Obsidian Glass Top Navigation */}
        <header className="sticky top-0 z-50 border-b border-glass-border bg-canvas-void/80 backdrop-blur-md px-6 py-3 flex items-center justify-between">
          <div className="flex items-center space-x-4">
            <div className="flex items-center space-x-2">
              <div className="w-3 h-3 rounded-full bg-cyan-400 shadow-glow-cyan animate-pulse"></div>
              <span className="font-bold text-lg tracking-wider text-white">PROJECT VULCAN</span>
            </div>
            <span className="text-xs px-2 py-0.5 rounded border border-cyan-500/30 bg-cyan-950/40 text-cyan-400 font-mono">
              PLATFORM OS v1.0
            </span>
            <span className="text-xs px-2 py-0.5 rounded border border-emerald-500/30 bg-emerald-950/40 text-emerald-400 font-mono">
              OCC/SOX COMPLIANT
            </span>
          </div>

          <div className="flex items-center space-x-6 text-xs font-mono">
            <div className="flex items-center space-x-2 text-slate-400">
              <span>MERKLE CHAIN:</span>
              <span className="text-emerald-400 font-semibold">VERIFIED</span>
            </div>
            <div className="flex items-center space-x-2 text-slate-400">
              <span>REDLOCK MUTEX:</span>
              <span className="text-cyan-400 font-semibold">QUORUM 5/5</span>
            </div>
            <div className="flex items-center space-x-2 text-slate-400">
              <span>OPERATOR:</span>
              <span className="text-amber-400 font-semibold">sre.lead@pnc.com</span>
            </div>
          </div>
        </header>

        {/* Main Application Canvas */}
        <main className="flex-1 p-6 max-w-7xl mx-auto w-full">
          {children}
        </main>

        <footer className="border-t border-glass-border py-3 px-6 text-center text-xs text-slate-500 font-mono">
          Project Vulcan • PNC Bank Enterprise Automation Control Plane • Uncle Bob • Alex Xu • Andrej Karpathy • Jordan Walke
        </footer>
      </body>
    </html>
  );
}

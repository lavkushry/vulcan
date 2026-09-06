'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { AppShell } from '@/components/layout/AppShell';

// This component acts as a client-side redirect from / to /history
function RedirectToHistory() {
  const router = useRouter();
  useEffect(() => {
    router.replace('/history');
  }, [router]);
  return (
    <div className="flex-1 flex items-center justify-center">
      <div className="flex items-center gap-3">
        <div className="w-3 h-3 rounded-full bg-cyan-400 animate-pulse" />
        <span className="text-sm text-slate-500 font-mono">Loading Vulcan…</span>
      </div>
    </div>
  );
}

export default function RootPage() {
  return (
    <AppShell>
      <RedirectToHistory />
    </AppShell>
  );
}

'use client';

import React, { Suspense } from 'react';
import { AppShell } from '@/components/layout/AppShell';
import { ExternalResourcesConsole } from '@/components/ExternalResourcesConsole';

export default function ExternalResourcesSettingsPage() {
  return (
    <AppShell>
      <Suspense fallback={<div className="p-8 text-center text-slate-500 font-mono text-xs">Loading external resources…</div>}>
        <ExternalResourcesConsole />
      </Suspense>
    </AppShell>
  );
}

'use client';

import React from 'react';
import { AppShell } from '@/components/layout/AppShell';
import { ExternalResourcesConsole } from '@/components/ExternalResourcesConsole';

export default function ExternalResourcesSettingsPage() {
  return (
    <AppShell>
      <ExternalResourcesConsole />
    </AppShell>
  );
}

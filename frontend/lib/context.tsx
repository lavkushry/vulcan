'use client';

import React, { createContext, useContext, useState, useCallback } from 'react';
import { DEMO_USERS } from '@/lib/api';

interface VulcanContextType {
  currentUser: string;
  setCurrentUser: (id: string) => void;
  paletteOpen: boolean;
  openPalette: () => void;
  closePalette: () => void;
}

const VulcanContext = createContext<VulcanContextType>({
  currentUser: DEMO_USERS[0].id,
  setCurrentUser: () => {},
  paletteOpen: false,
  openPalette: () => {},
  closePalette: () => {},
});

export function useVulcan() {
  return useContext(VulcanContext);
}

export function VulcanProvider({ children }: { children: React.ReactNode }) {
  const [currentUser, setCurrentUserState] = useState(DEMO_USERS[0].id);
  const [paletteOpen, setPaletteOpen] = useState(false);

  React.useEffect(() => {
    if (typeof window !== 'undefined') {
      const tok = window.localStorage.getItem('vulcan_api_token');
      if (tok) {
        if (tok.includes('dave') || tok.includes('admin')) setCurrentUserState('admin.dave');
        else if (tok.includes('alice') || tok.includes('operator')) setCurrentUserState('eng.alice');
        else if (tok.includes('bob') || tok.includes('lead')) setCurrentUserState('lead.bob');
        else if (tok.includes('carol') || tok.includes('sec')) setCurrentUserState('sec.carol');
        else if (tok.includes('emma') || tok.includes('audit')) setCurrentUserState('audit.emma');
        else if (tok.includes('bot')) setCurrentUserState('e2e.bot');
      }
    }
  }, []);

  const setCurrentUser = useCallback((id: string) => {
    setCurrentUserState(id);
    if (typeof window !== 'undefined') {
      const tokenMap: Record<string, string> = {
        'admin.dave': 'vlc_test_dave_ci_token',
        'eng.alice': 'vlc_test_alice_ci_token',
        'lead.bob': 'vlc_test_bob_ci_token',
        'sec.carol': 'vlc_test_carol_ci_token',
        'audit.emma': 'vlc_test_emma_ci_token',
        'e2e.bot': 'vlc_test_bot_ci_token',
      };
      if (tokenMap[id]) {
        window.localStorage.setItem('vulcan_api_token', tokenMap[id]);
      }
    }
  }, []);

  const openPalette = useCallback(() => setPaletteOpen(true), []);
  const closePalette = useCallback(() => setPaletteOpen(false), []);

  return (
    <VulcanContext.Provider value={{ currentUser, setCurrentUser, paletteOpen, openPalette, closePalette }}>
      {children}
    </VulcanContext.Provider>
  );
}

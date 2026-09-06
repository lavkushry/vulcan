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
  const [currentUser, setCurrentUser] = useState(DEMO_USERS[0].id);
  const [paletteOpen, setPaletteOpen] = useState(false);

  const openPalette = useCallback(() => setPaletteOpen(true), []);
  const closePalette = useCallback(() => setPaletteOpen(false), []);

  return (
    <VulcanContext.Provider value={{ currentUser, setCurrentUser, paletteOpen, openPalette, closePalette }}>
      {children}
    </VulcanContext.Provider>
  );
}

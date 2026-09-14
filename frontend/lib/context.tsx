'use client';

import React, { createContext, useContext, useState, useCallback, useEffect } from 'react';
import { DEMO_USERS } from '@/lib/api';

interface VulcanContextType {
  currentUser: string;
  setCurrentUser: (id: string) => void;
  paletteOpen: boolean;
  openPalette: () => void;
  closePalette: () => void;
  isDemoMode: boolean;
  setIsDemoMode: (val: boolean) => void;
  authenticatedUser: string | null;
  hasPermission: (permission: string) => boolean;
}

const VulcanContext = createContext<VulcanContextType>({
  currentUser: DEMO_USERS[0].id,
  setCurrentUser: () => {},
  paletteOpen: false,
  openPalette: () => {},
  closePalette: () => {},
  isDemoMode: true,
  setIsDemoMode: () => {},
  authenticatedUser: null,
  hasPermission: () => true,
});

export function useVulcan() {
  return useContext(VulcanContext);
}

// Map role to canonical permission strings
const ROLE_PERMISSIONS: Record<string, string[]> = {
  PLATFORM_ADMIN: ['job:create', 'job:approve', 'job:reject', 'job:execute', 'admin:access', 'resource:manage', 'policy:manage'],
  APPROVING_LEAD: ['job:create', 'job:approve', 'job:reject', 'job:execute'],
  SECURITY_ADMIN: ['job:create', 'job:reject', 'policy:manage', 'audit:view'],
  AUDITOR: ['audit:view', 'job:view'],
  OPERATOR: ['job:create', 'job:view'],
};

export function VulcanProvider({ children }: { children: React.ReactNode }) {
  const [currentUser, setCurrentUserState] = useState(DEMO_USERS[0].id);
  const [authenticatedUser, setAuthenticatedUser] = useState<string | null>(null);
  const [isDemoMode, setIsDemoMode] = useState<boolean>(true);
  const [paletteOpen, setPaletteOpen] = useState(false);

  // Initialize identity safely without overwriting stored real tokens
  useEffect(() => {
    if (typeof window === 'undefined') return;

    const realToken = window.localStorage.getItem('vulcan_api_token');
    const savedDemoUser = window.localStorage.getItem('vulcan_demo_user');

    const KNOWN_TOKEN_USERS: Record<string, string> = {
      'vlc_test_bot_ci_token': 'e2e.bot',
      'vlc_test_alice_ci_token': 'eng.alice',
      'vlc_test_bob_ci_token': 'lead.bob',
      'vlc_test_carol_ci_token': 'sec.carol',
      'vlc_test_dave_ci_token': 'admin.dave',
      'vlc_test_emma_ci_token': 'audit.emma',
      'vlc_MaC-NeYOOWXAtumu958dURAJT_SHpkVvPxBwjrNf93I': 'e2e.bot',
      'vlc_h_YYbbqDKf10OF2KmDQ7RhpTQwNxiEJpOHNgsKKkLyQ': 'eng.alice',
      'vlc_OFxJELOH-bDI-HkF-Ll87uW9xGay7QN4WomAkISebx4': 'lead.bob',
      'vlc__pjh-7D0PLeIoEqv1nSDth6X_enfz6IZlkHm33ivte4': 'admin.dave',
      'vlc_NPrvnYObqALxSieZi0v2l5VC7MWv8TMJdFnPUriUcLQ': 'sec.carol',
    };

    if (realToken && KNOWN_TOKEN_USERS[realToken]) {
      const matched = KNOWN_TOKEN_USERS[realToken];
      if (!savedDemoUser) {
        setCurrentUserState(matched);
      }
    } else if (realToken && !realToken.startsWith('vlc_test_')) {
      // Real authenticated token exists - treat as authenticated identity
      setIsDemoMode(false);
      const parsedUser = window.localStorage.getItem('vulcan_authenticated_user') || 'authenticated.user';
      setAuthenticatedUser(parsedUser);
      if (!savedDemoUser) {
        setCurrentUserState(parsedUser);
      }
    } else if (savedDemoUser && DEMO_USERS.some(u => u.id === savedDemoUser)) {
      // Restore selected demo user
      setCurrentUserState(savedDemoUser);
    }
  }, []);

  const setCurrentUser = useCallback((id: string) => {
    setCurrentUserState(id);
    if (typeof window !== 'undefined') {
      // Isolate demo identity selection so it never clobbers a real stored token
      window.localStorage.setItem('vulcan_demo_user', id);

      // Only set demo test token if no real user-supplied token is present
      const existingToken = window.localStorage.getItem('vulcan_api_token');
      const isCustomToken = existingToken && !existingToken.startsWith('vlc_test_');

      if (!isCustomToken) {
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
    }
  }, []);

  const hasPermission = useCallback((permission: string) => {
    const userObj = DEMO_USERS.find(u => u.id === currentUser);
    const role = userObj?.role || 'OPERATOR';
    const permissions = ROLE_PERMISSIONS[role] || [];
    return permissions.includes(permission);
  }, [currentUser]);

  const openPalette = useCallback(() => setPaletteOpen(true), []);
  const closePalette = useCallback(() => setPaletteOpen(false), []);

  return (
    <VulcanContext.Provider value={{
      currentUser,
      setCurrentUser,
      paletteOpen,
      openPalette,
      closePalette,
      isDemoMode,
      setIsDemoMode,
      authenticatedUser,
      hasPermission,
    }}>
      {children}
    </VulcanContext.Provider>
  );
}

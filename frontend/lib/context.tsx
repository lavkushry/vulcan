'use client';

import React, { createContext, useContext, useState, useCallback, useEffect } from 'react';
import { DEMO_USERS } from '@/lib/api';
import { getApiBaseUrl } from '@/lib/env';

export type AuthStatus = 'loading' | 'authenticated' | 'unauthenticated';

interface VulcanContextType {
  currentUser: string;
  setCurrentUser: (id: string) => void;
  paletteOpen: boolean;
  openPalette: () => void;
  closePalette: () => void;
  isDemoMode: boolean;
  setIsDemoMode: (val: boolean) => void;
  authenticatedUser: string | null;
  authenticatedRole: string | null;
  authenticatedRoleBadge: string | null;
  authStatus: AuthStatus;
  permissions: string[];
  hasPermission: (permission: string) => boolean;
  loginWithToken: (token: string) => Promise<{ success: boolean; error?: string }>;
  logout: () => void;
  isSignInModalOpen: boolean;
  openSignInModal: () => void;
  closeSignInModal: () => void;
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
  authenticatedRole: null,
  authenticatedRoleBadge: null,
  authStatus: 'loading',
  permissions: [],
  hasPermission: () => false,
  loginWithToken: async () => ({ success: false }),
  logout: () => {},
  isSignInModalOpen: false,
  openSignInModal: () => {},
  closeSignInModal: () => {},
});

export function useVulcan() {
  return useContext(VulcanContext);
}

export function VulcanProvider({ children }: { children: React.ReactNode }) {
  const [currentUser, setCurrentUserState] = useState(DEMO_USERS[0].id);
  const [authenticatedUser, setAuthenticatedUser] = useState<string | null>(null);
  const [authenticatedRole, setAuthenticatedRole] = useState<string | null>(null);
  const [authenticatedRoleBadge, setAuthenticatedRoleBadge] = useState<string | null>(null);
  const [permissions, setPermissions] = useState<string[]>([]);
  const [authStatus, setAuthStatus] = useState<AuthStatus>('loading');
  const [isDemoMode, setIsDemoMode] = useState<boolean>(true);
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [isSignInModalOpen, setIsSignInModalOpen] = useState(false);

  // Validate session against backend /api/v1/auth/session
  const checkSession = useCallback(async (suppliedToken?: string) => {
    if (typeof window === 'undefined') return;

    const realToken = suppliedToken ?? window.localStorage.getItem('vulcan_api_token');
    const envToken = process.env.NEXT_PUBLIC_VULCAN_API_TOKEN;
    const effectiveToken = realToken || envToken;

    if (!effectiveToken) {
      setAuthStatus('unauthenticated');
      setAuthenticatedUser(null);
      setAuthenticatedRole(null);
      setAuthenticatedRoleBadge(null);
      setPermissions([]);
      return;
    }

    try {
      const baseUrl = getApiBaseUrl();
      const res = await fetch(`${baseUrl}/api/v1/auth/session`, {
        headers: { Authorization: `Bearer ${effectiveToken}` },
      });

      if (res.ok) {
        const data = await res.json();
        if (data.authenticated) {
          setAuthStatus('authenticated');
          setAuthenticatedUser(data.user_id);
          setAuthenticatedRole(data.role);
          setAuthenticatedRoleBadge(data.role_badge);
          setPermissions(Array.isArray(data.permissions) ? data.permissions : []);
          setCurrentUserState(data.user_id);
          setIsDemoMode(false);
          return;
        }
      }

      // If response is unauthenticated or error: fail closed
      setAuthStatus('unauthenticated');
      setAuthenticatedUser(null);
      setAuthenticatedRole(null);
      setAuthenticatedRoleBadge(null);
      setPermissions([]);
      if (realToken && !suppliedToken) {
        window.localStorage.removeItem('vulcan_api_token');
      }
    } catch {
      // Backend unreachable or offline
      setAuthStatus('unauthenticated');
      setAuthenticatedUser(null);
      setAuthenticatedRole(null);
      setAuthenticatedRoleBadge(null);
      setPermissions([]);
    }
  }, []);

  useEffect(() => {
    checkSession();
  }, [checkSession]);

  // Demo user switcher for read-only preview — NEVER grants real administrative permissions!
  const setCurrentUser = useCallback((id: string) => {
    setCurrentUserState(id);
    if (typeof window !== 'undefined') {
      window.localStorage.setItem('vulcan_demo_user', id);
    }
  }, []);

  // Authenticate with a real API token
  const loginWithToken = useCallback(async (token: string): Promise<{ success: boolean; error?: string }> => {
    try {
      const baseUrl = getApiBaseUrl();
      const res = await fetch(`${baseUrl}/api/v1/auth/verify-token`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token: token.trim() }),
      });

      if (res.ok) {
        const data = await res.json();
        if (typeof window !== 'undefined') {
          window.localStorage.setItem('vulcan_api_token', token.trim());
        }
        setAuthStatus('authenticated');
        setAuthenticatedUser(data.user_id);
        setAuthenticatedRole(data.role);
        setAuthenticatedRoleBadge(data.role_badge);
        setPermissions(Array.isArray(data.permissions) ? data.permissions : []);
        setCurrentUserState(data.user_id);
        setIsDemoMode(false);
        setIsSignInModalOpen(false);
        return { success: true };
      } else {
        const err = await res.json().catch(() => ({}));
        return { success: false, error: err.detail || 'Invalid API token' };
      }
    } catch (e: any) {
      return { success: false, error: e.message || 'Connection failed' };
    }
  }, []);

  const logout = useCallback(() => {
    if (typeof window !== 'undefined') {
      window.localStorage.removeItem('vulcan_api_token');
      window.localStorage.removeItem('vulcan_authenticated_user');
    }
    setAuthStatus('unauthenticated');
    setAuthenticatedUser(null);
    setAuthenticatedRole(null);
    setAuthenticatedRoleBadge(null);
    setPermissions([]);
    setIsDemoMode(true);
    setCurrentUserState(DEMO_USERS[0].id);
  }, []);

  // Fails closed: unauthenticated sessions have ZERO mutation permissions!
  const hasPermission = useCallback((permission: string) => {
    if (authStatus !== 'authenticated') {
      return false;
    }
    return permissions.includes(permission);
  }, [authStatus, permissions]);

  const openPalette = useCallback(() => setPaletteOpen(true), []);
  const closePalette = useCallback(() => setPaletteOpen(false), []);
  const openSignInModal = useCallback(() => setIsSignInModalOpen(true), []);
  const closeSignInModal = useCallback(() => setIsSignInModalOpen(false), []);

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
      authenticatedRole,
      authenticatedRoleBadge,
      authStatus,
      permissions,
      hasPermission,
      loginWithToken,
      logout,
      isSignInModalOpen,
      openSignInModal,
      closeSignInModal,
    }}>
      {children}
    </VulcanContext.Provider>
  );
}

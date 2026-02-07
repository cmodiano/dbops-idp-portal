import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import type { NavigationTabKey, User } from '../types/common';
import { BUSINESS_PROFILES } from '../types/common';
import { setAuthAccessors } from '../services/api_client';
import { refreshAccessToken, fetchCurrentUser as fetchUser, logoutApi } from '../services/auth_service';
import logger from '../services/logger';

// DEV MODE: Skip SAML authentication and use a mock DBOPS user
// Enable by setting VITE_DEV_AUTH=true in .env.local or environment
// Disabled in test mode to allow proper auth testing
const DEV_AUTH_ENABLED = import.meta.env.VITE_DEV_AUTH === 'true' && import.meta.env.MODE !== 'test';

const DEV_MOCK_USER: User = {
  id: 1,
  username: 'dev.dbops',
  display_name: 'Dev DBOPS User',
  profile: 'dbops',
  navigation_tabs: ['catalog', 'executions', 'calendar', 'dashboard', 'admin', 'audit'],
  is_auditor: true, // Story 6.3: enable audit tab in dev mode
};

const DEV_MOCK_TOKEN = 'dev-mock-token-for-testing';

interface AuthContextValue {
  user: User | null;
  accessToken: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: () => void;
  logout: () => Promise<void>;
  refreshToken: () => Promise<string | null>;
  hasTab: (tabKey: NavigationTabKey) => boolean;
  /** Story 7.1: true if user has a business profile (simplified UI). */
  isBusinessProfile: boolean;
}

const AuthContext = createContext<AuthContextValue>({
  user: null,
  accessToken: null,
  isAuthenticated: false,
  isLoading: true,
  login: () => {},
  logout: async () => {},
  refreshToken: async () => null,
  hasTab: () => false,
  isBusinessProfile: false,
});

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [accessToken, setAccessToken] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const tokenRef = useRef<string | null>(null);

  // Keep ref in sync for non-React consumers (api_client)
  useEffect(() => {
    tokenRef.current = accessToken;
  }, [accessToken]);

  const login = useCallback(() => {
    window.location.href = '/api/v1/auth/saml/login/';
  }, []);

  const refreshTokenFn = useCallback(async (): Promise<string | null> => {
    const token = await refreshAccessToken();
    setAccessToken(token);
    return token;
  }, []);

  const fetchCurrentUserFn = useCallback(async (token: string): Promise<User | null> => {
    return fetchUser(token);
  }, []);

  const logout = useCallback(async () => {
    try {
      await logoutApi();
    } catch {
      // Best effort
    }
    setUser(null);
    setAccessToken(null);
    window.location.href = '/login';
  }, []);

  // Wire api_client to use current token and refresh function
  // Update whenever token or refresh function changes
  useEffect(() => {
    setAuthAccessors(() => tokenRef.current, refreshTokenFn);
  }, [accessToken, refreshTokenFn]);

  // Silent refresh on mount to restore session from httpOnly cookie
  // In DEV_AUTH mode, skip API calls and use mock user
  useEffect(() => {
    let cancelled = false;

    async function tryRestore() {
      // DEV MODE: Use mock user without API calls
      if (DEV_AUTH_ENABLED) {
        if (!cancelled) {
          logger.debug('DEV AUTH - Using mock DBOPS user, SAML bypassed');
          setAccessToken(DEV_MOCK_TOKEN);
          setUser(DEV_MOCK_USER);
          setIsLoading(false);
        }
        return;
      }

      const token = await refreshTokenFn();
      if (cancelled) return;

      if (token) {
        const userData = await fetchCurrentUserFn(token);
        if (!cancelled) {
          setUser(userData);
        }
      }
      if (!cancelled) {
        setIsLoading(false);
      }
    }

    tryRestore();
    return () => { cancelled = true; };
  }, [refreshTokenFn, fetchCurrentUserFn]);

  // Handle auth callback: extract access_token from URL fragment (AC #4)
  // Token is passed via URL fragment (not query param) for security - fragments
  // are not sent to server, only accessible via JavaScript
  useEffect(() => {
    const hash = window.location.hash;
    if (hash.includes('access_token=')) {
      // Parse URL fragment: #access_token=TOKEN&other=params
      const tokenMatch = hash.match(/access_token=([^&]+)/);
      const token = tokenMatch ? tokenMatch[1] : null;
      if (token) {
        queueMicrotask(() => setAccessToken(token));
        // Clean URL fragment immediately after extraction
        window.history.replaceState(null, '', window.location.pathname);
        // Fetch user profile with the extracted token
        fetchCurrentUserFn(token).then(setUser);
      }
    }
  }, [fetchCurrentUserFn]);

  const hasTab = useCallback(
    (tabKey: NavigationTabKey): boolean => {
      return user?.navigation_tabs?.includes(tabKey) ?? false;
    },
    [user],
  );

  // Story 7.1: Determine if user has a business profile (simplified UI)
  // Uses backend-provided flag if available, otherwise falls back to local profile check
  const isBusinessProfile = useMemo(() => {
    if (!user) return false;
    // Prefer backend-provided flag (AC5: RBAC from API)
    if (typeof user.is_business_profile === 'boolean') {
      return user.is_business_profile;
    }
    // Fallback: check profile against known business profiles
    return BUSINESS_PROFILES.includes(user.profile);
  }, [user]);

  const value: AuthContextValue = {
    user,
    accessToken,
    isAuthenticated: !!user && !!accessToken,
    isLoading,
    login,
    logout,
    refreshToken: refreshTokenFn,
    hasTab,
    isBusinessProfile,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

/* eslint-disable-next-line react-refresh/only-export-components -- useAuth is the standard context consumer pattern */
export function useAuth() {
  return useContext(AuthContext);
}

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import type { NavigationTabKey, User } from '../types/common';
import { BUSINESS_PROFILES } from '../types/common';
import { setAuthAccessors } from '../services/api_client';
import { refreshAccessToken, fetchCurrentUser as fetchUser, logoutApi, portalLogin } from '../services/auth_service';
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
  loginWithCredentials: (username: string, password: string) => Promise<void>;
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
  loginWithCredentials: async () => {},
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

  /** Promise-based mutex: prevents concurrent refresh calls (CRIT-3 fix).
   *  When multiple 401 responses trigger simultaneous refresh attempts,
   *  only the first creates a new refresh request — subsequent calls
   *  return the same in-flight promise. Reset after completion to allow future refreshes.
   *
   *  Uses `useRef` instead of module-level variable to ensure one mutex per AuthProvider instance.
   *  React guarantees `.current` stability across renders, so concurrent calls share the same ref. */
  const refreshPromiseRef = useRef<Promise<string | null> | null>(null);
  const cancelledRef = useRef(false);

  /**
   * Refresh the access token using the httpOnly refresh cookie.
   * Uses a promise-based mutex so concurrent callers share a single request.
   * @returns The new access token, or null if refresh failed.
   */
  const refreshTokenFn = useCallback(async (): Promise<string | null> => {
    const correlationId = crypto.randomUUID();

    // If a refresh is already in progress, wait for the existing promise
    if (refreshPromiseRef.current) {
      logger.debug('Token refresh already in progress, waiting for existing promise', { correlation_id: correlationId });
      return refreshPromiseRef.current;
    }

    // Create a new refresh promise and store it in the mutex
    logger.debug('Starting token refresh', { correlation_id: correlationId });
    const promise = refreshAccessToken()
      .then((token) => {
        // Check if component was unmounted during refresh
        if (cancelledRef.current) {
          logger.debug('Token refresh completed but component unmounted, skipping state update', { correlation_id: correlationId });
          return null;
        }

        try {
          setAccessToken(token);
          logger.info('Token refresh completed', { success: !!token, correlation_id: correlationId });
        } catch (err) {
          logger.error('Failed to set access token after refresh', {
            error: err instanceof Error ? err.message : String(err),
            correlation_id: correlationId
          });
          return null;
        }

        // Reset mutex before returning (success path)
        refreshPromiseRef.current = null;
        return token;
      })
      .catch((err) => {
        logger.error('Token refresh failed', {
          error: err instanceof Error ? err.message : String(err),
          correlation_id: correlationId
        });
        // Reset mutex before returning (failure path)
        refreshPromiseRef.current = null;
        return null;
      });

    refreshPromiseRef.current = promise;
    return promise;
  }, []);

  const fetchCurrentUserFn = useCallback(async (token: string): Promise<User | null> => {
    return fetchUser(token);
  }, []);

  const loginWithCredentials = useCallback(async (username: string, password: string) => {
    const data = await portalLogin(username, password);
    setAccessToken(data.access_token);
    const userData = await fetchCurrentUserFn(data.access_token);
    if (!userData) {
      setAccessToken(null);
      throw new Error('Impossible de récupérer le profil utilisateur.');
    }
    setUser(userData);
    // Navigation vers /catalog gérée par le composant appelant après succès
  }, [fetchCurrentUserFn]);

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
    cancelledRef.current = false;

    async function tryRestore() {
      // DEV MODE: Use mock user without API calls
      if (DEV_AUTH_ENABLED) {
        if (!cancelledRef.current) {
          logger.debug('DEV AUTH - Using mock DBOPS user, SAML bypassed');
          setAccessToken(DEV_MOCK_TOKEN);
          setUser(DEV_MOCK_USER);
          setIsLoading(false);
        }
        return;
      }

      const token = await refreshTokenFn();
      if (cancelledRef.current) return;

      if (token) {
        const userData = await fetchCurrentUserFn(token);
        if (!cancelledRef.current) {
          setUser(userData);
        }
      }
      if (!cancelledRef.current) {
        setIsLoading(false);
      }
    }

    tryRestore();
    return () => { cancelledRef.current = true; };
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
    loginWithCredentials,
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

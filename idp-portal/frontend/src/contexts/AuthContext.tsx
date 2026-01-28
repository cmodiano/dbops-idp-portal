import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from 'react';
import type { NavigationTabKey, User } from '../types/common';
import { setAuthAccessors } from '../services/api_client';
import { refreshAccessToken, fetchCurrentUser as fetchUser, logoutApi } from '../services/auth_service';

interface AuthContextValue {
  user: User | null;
  accessToken: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: () => void;
  logout: () => Promise<void>;
  refreshToken: () => Promise<string | null>;
  hasTab: (tabKey: NavigationTabKey) => boolean;
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
    window.location.href = '/api/v1/auth/saml/login';
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
  useEffect(() => {
    setAuthAccessors(() => tokenRef.current, refreshTokenFn);
  }, [refreshTokenFn]);

  // Silent refresh on mount to restore session from httpOnly cookie
  useEffect(() => {
    let cancelled = false;

    async function tryRestore() {
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
        setAccessToken(token);
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

  const value: AuthContextValue = {
    user,
    accessToken,
    isAuthenticated: !!user && !!accessToken,
    isLoading,
    login,
    logout,
    refreshToken: refreshTokenFn,
    hasTab,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  return useContext(AuthContext);
}

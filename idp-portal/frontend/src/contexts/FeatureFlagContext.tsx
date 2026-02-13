/**
 * Story 17.12: Feature Flag Context.
 *
 * Provides feature flag state to the entire application via React Context.
 * Auto-refreshes flag status periodically (default 5 minutes).
 */

import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from 'react';
import { fetchFeatureFlagsStatus, type FeatureFlagsStatus } from '../services/featureFlagService';
import { useAuth } from './AuthContext';
import logger from '../services/logger';

const REFRESH_INTERVAL_MS = 5 * 60 * 1000; // 5 minutes

interface FeatureFlagContextValue {
  /** Map of flag_key -> boolean (enabled for current user). */
  flags: FeatureFlagsStatus;
  /** Check if a specific flag is enabled. Returns false for unknown flags. */
  isEnabled: (flagKey: string) => boolean;
  /** Whether the initial flags have been loaded. */
  isLoading: boolean;
  /** Force refresh flags from server. */
  refresh: () => Promise<void>;
}

const FeatureFlagContext = createContext<FeatureFlagContextValue>({
  flags: {},
  isEnabled: () => false,
  isLoading: true,
  refresh: async () => {},
});

/* eslint-disable-next-line react-refresh/only-export-components */
export function useFeatureFlag(flagKey: string): boolean {
  const { isEnabled } = useContext(FeatureFlagContext);
  return isEnabled(flagKey);
}

/* eslint-disable-next-line react-refresh/only-export-components */
export function useFeatureFlags(): FeatureFlagsStatus {
  const { flags } = useContext(FeatureFlagContext);
  return flags;
}

/* eslint-disable-next-line react-refresh/only-export-components */
export function useFeatureFlagContext(): FeatureFlagContextValue {
  return useContext(FeatureFlagContext);
}

export function FeatureFlagProvider({ children }: { children: ReactNode }) {
  const { isAuthenticated } = useAuth();
  const [flags, setFlags] = useState<FeatureFlagsStatus>({});
  const [isLoading, setIsLoading] = useState(true);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const refresh = useCallback(async () => {
    if (!isAuthenticated) {
      setFlags({});
      setIsLoading(false);
      return;
    }
    try {
      const data = await fetchFeatureFlagsStatus();
      setFlags(data);
    } catch (err) {
      logger.warn('feature_flags_fetch_error', { error: String(err) });
    } finally {
      setIsLoading(false);
    }
  }, [isAuthenticated]);

  // Initial load and periodic refresh
  useEffect(() => {
    refresh();

    if (isAuthenticated) {
      intervalRef.current = setInterval(refresh, REFRESH_INTERVAL_MS);
    }

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    };
  }, [isAuthenticated, refresh]);

  const isEnabled = useCallback(
    (flagKey: string): boolean => flags[flagKey] === true,
    [flags],
  );

  const value: FeatureFlagContextValue = {
    flags,
    isEnabled,
    isLoading,
    refresh,
  };

  return (
    <FeatureFlagContext.Provider value={value}>
      {children}
    </FeatureFlagContext.Provider>
  );
}

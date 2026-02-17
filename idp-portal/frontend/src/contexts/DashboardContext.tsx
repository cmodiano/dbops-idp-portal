/**
 * DashboardContext - Shared state for dashboard badge (Story 5.2, Task 3.1).
 *
 * Manages the count of unseen error executions for the badge display.
 * Uses localStorage to persist seen errors across sessions.
 */

import { createContext, useContext, useState, useCallback, useEffect, type ReactNode } from 'react';

const LOCALSTORAGE_KEY = 'dbops_dashboard_seen_errors';

interface DashboardContextValue {
  /** Number of unseen error executions (for badge). */
  unseenErrorCount: number;
  /** Add an error execution ID to unseen list. */
  addUnseenError: (executionId: number) => void;
  /** Mark all errors as seen (clear badge). */
  markAllSeen: () => void;
  /** Check if an execution ID is in unseen errors. */
  hasUnseenError: (executionId: number) => boolean;
}

const DashboardContext = createContext<DashboardContextValue | null>(null);

export function DashboardProvider({ children }: { children: ReactNode }) {
  const [unseenErrorIds, setUnseenErrorIds] = useState<Set<number>>(() => {
    // Load from localStorage on init
    try {
      const stored = localStorage.getItem(LOCALSTORAGE_KEY);
      if (stored) {
        const ids = JSON.parse(stored) as number[];
        return new Set(ids);
      }
    } catch {
      // Ignore parse errors
    }
    return new Set();
  });

  // Persist to localStorage on change
  useEffect(() => {
    try {
      const ids = Array.from(unseenErrorIds);
      localStorage.setItem(LOCALSTORAGE_KEY, JSON.stringify(ids));
    } catch {
      // Ignore storage errors
    }
  }, [unseenErrorIds]);

  const addUnseenError = useCallback((executionId: number) => {
    setUnseenErrorIds((prev) => {
      const next = new Set(prev);
      next.add(executionId);
      return next;
    });
  }, []);

  const markAllSeen = useCallback(() => {
    setUnseenErrorIds(new Set());
  }, []);

  const hasUnseenError = useCallback(
    (executionId: number) => unseenErrorIds.has(executionId),
    [unseenErrorIds]
  );

  const value: DashboardContextValue = {
    unseenErrorCount: unseenErrorIds.size,
    addUnseenError,
    markAllSeen,
    hasUnseenError,
  };

  return (
    <DashboardContext.Provider value={value}>
      {children}
    </DashboardContext.Provider>
  );
}

/* eslint-disable-next-line react-refresh/only-export-components -- useDashboard is the standard context consumer pattern */
export function useDashboard(): DashboardContextValue {
  const context = useContext(DashboardContext);
  if (!context) {
    throw new Error('useDashboard must be used within a DashboardProvider');
  }
  return context;
}

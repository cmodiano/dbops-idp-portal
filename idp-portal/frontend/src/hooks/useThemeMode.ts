/**
 * useThemeMode - Hook for managing theme mode (light/dark/system).
 * Story 2-15, Task 1.1
 *
 * - Persists preference in localStorage (key: idp-portal-theme)
 * - Listens to prefers-color-scheme for system mode
 * - Returns both mode and effectiveMode (resolved light/dark)
 */

import { useState, useEffect, useCallback } from 'react';

export type ThemeMode = 'light' | 'dark' | 'system';
export type EffectiveThemeMode = 'light' | 'dark';

const STORAGE_KEY = 'idp-portal-theme-v1';

/**
 * Gets the system color scheme preference.
 */
function getSystemPreference(): EffectiveThemeMode {
  if (typeof window === 'undefined') return 'light';
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}

/**
 * Reads stored theme mode from localStorage.
 */
function getStoredMode(): ThemeMode {
  if (typeof window === 'undefined') return 'system';
  const stored = localStorage.getItem(STORAGE_KEY);
  if (stored === 'light' || stored === 'dark' || stored === 'system') {
    return stored;
  }
  return 'system';
}

export interface UseThemeModeReturn {
  /** Current mode setting (light, dark, or system) */
  mode: ThemeMode;
  /** Resolved mode (always light or dark) */
  effectiveMode: EffectiveThemeMode;
  /** Set mode to light, dark, or system */
  setMode: (mode: ThemeMode) => void;
  /** Toggle between light and dark (ignores system) */
  toggleTheme: () => void;
}

/**
 * Hook for managing theme mode with localStorage persistence
 * and system preference detection.
 */
export function useThemeMode(): UseThemeModeReturn {
  const [mode, setModeState] = useState<ThemeMode>(getStoredMode);
  const [systemPreference, setSystemPreference] = useState<EffectiveThemeMode>(getSystemPreference);

  // Listen to system preference changes
  useEffect(() => {
    const mq = window.matchMedia('(prefers-color-scheme: dark)');
    const handler = (e: MediaQueryListEvent) => {
      setSystemPreference(e.matches ? 'dark' : 'light');
    };
    mq.addEventListener('change', handler);
    return () => mq.removeEventListener('change', handler);
  }, []);

  // Compute effective mode
  const effectiveMode: EffectiveThemeMode = mode === 'system' ? systemPreference : mode;

  // Set mode with persistence
  const setMode = useCallback((newMode: ThemeMode) => {
    setModeState(newMode);
    localStorage.setItem(STORAGE_KEY, newMode);
  }, []);

  // Toggle between light and dark
  const toggleTheme = useCallback(() => {
    const newMode: ThemeMode = effectiveMode === 'light' ? 'dark' : 'light';
    setMode(newMode);
  }, [effectiveMode, setMode]);

  return { mode, effectiveMode, setMode, toggleTheme };
}

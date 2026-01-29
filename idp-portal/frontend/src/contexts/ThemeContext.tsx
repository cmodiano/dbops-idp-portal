/**
 * ThemeContext - React context for theme management.
 * Story 2-15, Task 1.2
 *
 * Provides theme mode and toggle functionality to all components.
 */

import { createContext, useContext, type ReactNode } from 'react';
import { useThemeMode, type ThemeMode, type EffectiveThemeMode } from '../hooks/useThemeMode';

export interface ThemeContextValue {
  /** Current mode setting (light, dark, or system) */
  mode: ThemeMode;
  /** Resolved mode (always light or dark) */
  effectiveMode: EffectiveThemeMode;
  /** Set mode to light, dark, or system */
  setMode: (mode: ThemeMode) => void;
  /** Toggle between light and dark */
  toggleTheme: () => void;
}

const ThemeContext = createContext<ThemeContextValue | null>(null);

export interface ThemeProviderProps {
  children: ReactNode;
}

/**
 * Provider component for theme context.
 * Wrap your app with this to enable theme switching.
 */
export function ThemeProvider({ children }: ThemeProviderProps) {
  const { mode, effectiveMode, setMode, toggleTheme } = useThemeMode();

  const value: ThemeContextValue = {
    mode,
    effectiveMode,
    setMode,
    toggleTheme,
  };

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

/**
 * Hook to access theme context.
 * Must be used within a ThemeProvider.
 * @throws Error if used outside of ThemeProvider
 */
export function useTheme(): ThemeContextValue {
  const context = useContext(ThemeContext);
  if (context === null) {
    throw new Error('useTheme must be used within a ThemeProvider');
  }
  return context;
}

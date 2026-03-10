import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useThemeMode } from './useThemeMode';

describe('useThemeMode', () => {
  let mockMatchMedia: ReturnType<typeof vi.fn>;
  let mockAddEventListener: ReturnType<typeof vi.fn>;
  let mockRemoveEventListener: ReturnType<typeof vi.fn>;
  let mediaQueryCallback: ((e: MediaQueryListEvent) => void) | null = null;

  beforeEach(() => {
    // Clear localStorage
    localStorage.clear();

    // Mock matchMedia
    mockAddEventListener = vi.fn((_, callback) => {
      mediaQueryCallback = callback;
    });
    mockRemoveEventListener = vi.fn();
    mockMatchMedia = vi.fn().mockImplementation((query: string) => ({
      matches: query.includes('dark') ? false : true, // Default to light system preference
      media: query,
      addEventListener: mockAddEventListener,
      removeEventListener: mockRemoveEventListener,
    }));
    window.matchMedia = mockMatchMedia as unknown as typeof window.matchMedia;
  });

  afterEach(() => {
    vi.restoreAllMocks();
    mediaQueryCallback = null;
  });

  it('defaults to system mode when no localStorage value (AC #3)', () => {
    const { result } = renderHook(() => useThemeMode());
    expect(result.current.mode).toBe('system');
  });

  it('resolves effectiveMode based on system preference (AC #3)', () => {
    // Mock dark system preference
    mockMatchMedia.mockImplementation((query: string) => ({
      matches: query.includes('dark'),
      media: query,
      addEventListener: mockAddEventListener,
      removeEventListener: mockRemoveEventListener,
    }));

    const { result } = renderHook(() => useThemeMode());
    expect(result.current.mode).toBe('system');
    expect(result.current.effectiveMode).toBe('dark');
  });

  it('reads initial mode from localStorage (AC #2)', () => {
    localStorage.setItem('idp-portal-theme-v1', 'dark');
    const { result } = renderHook(() => useThemeMode());
    expect(result.current.mode).toBe('dark');
    expect(result.current.effectiveMode).toBe('dark');
  });

  it('persists mode to localStorage when setMode is called (AC #2)', () => {
    const { result } = renderHook(() => useThemeMode());

    act(() => {
      result.current.setMode('dark');
    });

    expect(localStorage.getItem('idp-portal-theme-v1')).toBe('dark');
    expect(result.current.mode).toBe('dark');
    expect(result.current.effectiveMode).toBe('dark');
  });

  it('toggleTheme switches between light and dark (AC #1)', () => {
    const { result } = renderHook(() => useThemeMode());

    // Start at light (system default)
    expect(result.current.effectiveMode).toBe('light');

    act(() => {
      result.current.toggleTheme();
    });

    expect(result.current.effectiveMode).toBe('dark');
    expect(result.current.mode).toBe('dark');

    act(() => {
      result.current.toggleTheme();
    });

    expect(result.current.effectiveMode).toBe('light');
    expect(result.current.mode).toBe('light');
  });

  it('responds to system preference changes when mode is system', () => {
    const { result } = renderHook(() => useThemeMode());

    expect(result.current.mode).toBe('system');
    expect(result.current.effectiveMode).toBe('light');

    // Simulate system preference change to dark
    act(() => {
      mediaQueryCallback?.({ matches: true } as MediaQueryListEvent);
    });

    expect(result.current.effectiveMode).toBe('dark');
  });

  it('ignores invalid localStorage values', () => {
    localStorage.setItem('idp-portal-theme-v1', 'invalid-value');
    const { result } = renderHook(() => useThemeMode());
    expect(result.current.mode).toBe('system');
  });

  it('cleans up event listener on unmount', () => {
    const { unmount } = renderHook(() => useThemeMode());
    unmount();
    expect(mockRemoveEventListener).toHaveBeenCalled();
  });
});

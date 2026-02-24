/**
 * Tests for useMediaQuery hook (Story 39.7 — coverage).
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useMediaQuery } from './useMediaQuery';

describe('useMediaQuery', () => {
  let mockAddEventListener: ReturnType<typeof vi.fn>;
  let mockRemoveEventListener: ReturnType<typeof vi.fn>;
  let changeHandler: ((e: MediaQueryListEvent) => void) | null = null;
  let mockMatches = false;

  beforeEach(() => {
    mockAddEventListener = vi.fn((event, handler) => {
      if (event === 'change') changeHandler = handler as (e: MediaQueryListEvent) => void;
    });
    mockRemoveEventListener = vi.fn();
    changeHandler = null;
    mockMatches = false;

    vi.spyOn(window, 'matchMedia').mockImplementation(((query: string) => ({
      matches: mockMatches,
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: mockAddEventListener,
      removeEventListener: mockRemoveEventListener,
      dispatchEvent: vi.fn(),
    })) as unknown as (query: string) => MediaQueryList);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('returns false when matchMedia does not match', () => {
    mockMatches = false;
    const { result } = renderHook(() => useMediaQuery(1280));
    expect(result.current).toBe(false);
  });

  it('returns true when matchMedia matches', async () => {
    mockMatches = true;
    const { result } = renderHook(() => useMediaQuery(1280));
    // After queueMicrotask, the state is updated
    await act(async () => {
      await new Promise((r) => setTimeout(r, 0));
    });
    expect(result.current).toBe(true);
  });

  it('uses default minWidth of 1280', () => {
    const { result } = renderHook(() => useMediaQuery());
    expect(result.current).toBe(false);
    expect(window.matchMedia).toHaveBeenCalledWith('(min-width: 1280px)');
  });

  it('uses custom minWidth', () => {
    renderHook(() => useMediaQuery(768));
    expect(window.matchMedia).toHaveBeenCalledWith('(min-width: 768px)');
  });

  it('registers and uses event listener for change events', async () => {
    mockMatches = false;
    renderHook(() => useMediaQuery(1280));

    // Ensure effect has run and changeHandler is captured
    expect(mockAddEventListener).toHaveBeenCalledWith('change', expect.any(Function));
    // The changeHandler should be a function
    expect(typeof changeHandler).toBe('function');
  });

  it('removes event listener on unmount', () => {
    const { unmount } = renderHook(() => useMediaQuery(1280));
    unmount();
    expect(mockRemoveEventListener).toHaveBeenCalledWith('change', expect.any(Function));
  });

  it('registers event listener on mount', () => {
    renderHook(() => useMediaQuery(1280));
    expect(mockAddEventListener).toHaveBeenCalledWith('change', expect.any(Function));
  });

  it('updates when set to false via change event', async () => {
    mockMatches = true;
    const { result } = renderHook(() => useMediaQuery(1280));

    await act(async () => {
      await new Promise((r) => setTimeout(r, 0));
    });
    expect(result.current).toBe(true);

    await act(async () => {
      changeHandler?.({ matches: false } as MediaQueryListEvent);
    });

    expect(result.current).toBe(false);
  });
});

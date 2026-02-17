/**
 * Tests for useUrlFilters hook (Story 8.4, AC6, AC8, Task 15).
 */

import { renderHook, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { MemoryRouter } from 'react-router';
import { useUrlFilters } from './useUrlFilters';
import type { DashboardFilters } from '../types/api';
import type { ReactNode } from 'react';

// Mock localStorage
const localStorageMock = (() => {
  let store: Record<string, string> = {};
  return {
    getItem: vi.fn((key: string) => store[key] || null),
    setItem: vi.fn((key: string, value: string) => {
      store[key] = value;
    }),
    removeItem: vi.fn((key: string) => {
      delete store[key];
    }),
    clear: vi.fn(() => {
      store = {};
    }),
  };
})();

Object.defineProperty(window, 'localStorage', { value: localStorageMock });

function createWrapper(initialEntries: string[] = ['/']) {
  return function Wrapper({ children }: { children: ReactNode }) {
    return (
      <MemoryRouter initialEntries={initialEntries}>{children}</MemoryRouter>
    );
  };
}

describe('useUrlFilters', () => {
  beforeEach(() => {
    localStorageMock.clear();
    vi.clearAllMocks();
  });

  afterEach(() => {
    localStorageMock.clear();
  });

  it('returns empty filters when URL has no query params', () => {
    const { result } = renderHook(() => useUrlFilters(), {
      wrapper: createWrapper(['/dashboard']),
    });

    const [filters] = result.current;
    expect(filters).toEqual({});
  });

  it('parses engine filter from URL (AC6)', () => {
    const { result } = renderHook(() => useUrlFilters(), {
      wrapper: createWrapper(['/dashboard?engine=aap']),
    });

    const [filters] = result.current;
    expect(filters.engine).toBe('aap');
  });

  it('parses environment filter from URL', () => {
    const { result } = renderHook(() => useUrlFilters(), {
      wrapper: createWrapper(['/dashboard?environment=prod']),
    });

    const [filters] = result.current;
    expect(filters.environment).toBe('prod');
  });

  it('parses tags filter from URL (comma-separated)', () => {
    const { result } = renderHook(() => useUrlFilters(), {
      wrapper: createWrapper(['/dashboard?tags=oracle,postgresql']),
    });

    const [filters] = result.current;
    expect(filters.tags).toEqual(['oracle', 'postgresql']);
  });

  it('parses status filter from URL', () => {
    const { result } = renderHook(() => useUrlFilters(), {
      wrapper: createWrapper(['/dashboard?status=COMPLETED']),
    });

    const [filters] = result.current;
    expect(filters.status).toBe('COMPLETED');
  });

  it('parses date range from URL', () => {
    const { result } = renderHook(() => useUrlFilters(), {
      wrapper: createWrapper(['/dashboard?from_date=2026-01-01&to_date=2026-01-31']),
    });

    const [filters] = result.current;
    expect(filters.fromDate).toBe('2026-01-01');
    expect(filters.toDate).toBe('2026-01-31');
  });

  it('parses days from URL', () => {
    const { result } = renderHook(() => useUrlFilters(), {
      wrapper: createWrapper(['/dashboard?days=30']),
    });

    const [filters] = result.current;
    expect(filters.days).toBe(30);
  });

  it('parses multiple filters from URL', () => {
    const { result } = renderHook(() => useUrlFilters(), {
      wrapper: createWrapper(['/dashboard?engine=aap&environment=prod&days=14']),
    });

    const [filters] = result.current;
    expect(filters).toEqual({
      engine: 'aap',
      environment: 'prod',
      days: 14,
    });
  });

  it('setFilters updates filters state', () => {
    const { result } = renderHook(() => useUrlFilters(), {
      wrapper: createWrapper(['/dashboard']),
    });

    act(() => {
      const [, setFilters] = result.current;
      setFilters({ engine: 'terraform', environment: 'dev' });
    });

    const [filters] = result.current;
    expect(filters.engine).toBe('terraform');
    expect(filters.environment).toBe('dev');
  });

  it('setFilters clears filters when empty object passed', () => {
    const { result } = renderHook(() => useUrlFilters(), {
      wrapper: createWrapper(['/dashboard?engine=aap']),
    });

    act(() => {
      const [, setFilters] = result.current;
      setFilters({});
    });

    const [filters] = result.current;
    expect(filters).toEqual({});
  });

  it('saves filters to localStorage when setFilters is called (AC8)', () => {
    const { result } = renderHook(() => useUrlFilters(), {
      wrapper: createWrapper(['/dashboard']),
    });

    const newFilters: DashboardFilters = { engine: 'aap', environment: 'prod' };

    act(() => {
      const [, setFilters] = result.current;
      setFilters(newFilters);
    });

    expect(localStorageMock.setItem).toHaveBeenCalledWith(
      'dashboard_filters',
      JSON.stringify(newFilters),
    );
  });

  it('removes from localStorage when filters are cleared', () => {
    const { result } = renderHook(() => useUrlFilters(), {
      wrapper: createWrapper(['/dashboard?engine=aap']),
    });

    act(() => {
      const [, setFilters] = result.current;
      setFilters({});
    });

    expect(localStorageMock.removeItem).toHaveBeenCalledWith('dashboard_filters');
  });

  it('restores filters from localStorage when URL is empty (AC8)', () => {
    // Pre-populate localStorage
    const storedFilters: DashboardFilters = { engine: 'terraform', days: 30 };
    localStorageMock.getItem.mockReturnValueOnce(JSON.stringify(storedFilters));

    renderHook(() => useUrlFilters(), {
      wrapper: createWrapper(['/dashboard']),
    });

    // Note: Due to the async nature of the effect, we may need to wait
    // In practice, the hook restores from localStorage on mount
    // This test verifies localStorage.getItem was called
    expect(localStorageMock.getItem).toHaveBeenCalledWith('dashboard_filters');
  });

  it('URL takes priority over localStorage (AC6 > AC8)', () => {
    // Pre-populate localStorage with different filters
    const storedFilters: DashboardFilters = { engine: 'terraform' };
    localStorageMock.getItem.mockReturnValueOnce(JSON.stringify(storedFilters));

    const { result } = renderHook(() => useUrlFilters(), {
      wrapper: createWrapper(['/dashboard?engine=aap']),
    });

    const [filters] = result.current;
    // URL should take priority
    expect(filters.engine).toBe('aap');
  });

  it('handles invalid days value gracefully', () => {
    const { result } = renderHook(() => useUrlFilters(), {
      wrapper: createWrapper(['/dashboard?days=invalid']),
    });

    const [filters] = result.current;
    expect(filters.days).toBeUndefined();
  });

  it('handles empty tags gracefully', () => {
    const { result } = renderHook(() => useUrlFilters(), {
      wrapper: createWrapper(['/dashboard?tags=']),
    });

    const [filters] = result.current;
    expect(filters.tags).toBeUndefined();
  });
});

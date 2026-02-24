/**
 * Tests for useExecutionFilters hook (Story 39.7 — coverage).
 */
import { describe, it, expect } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import React from 'react';
import { MemoryRouter } from 'react-router';
import { useExecutionFilters } from './useExecutionFilters';

function createWrapper(initialEntries: string[] = ['/']) {
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return React.createElement(MemoryRouter, { initialEntries }, children);
  };
}

describe('useExecutionFilters', () => {
  it('returns default filters with empty URL', () => {
    const { result } = renderHook(() => useExecutionFilters(), {
      wrapper: createWrapper(['/']),
    });
    expect(result.current.filters.status).toBeNull();
    expect(result.current.filters.environment).toBeNull();
    expect(result.current.activeFilterCount).toBe(0);
    expect(result.current.hasActiveFilters).toBe(false);
  });

  it('parses filters from URL query params', () => {
    const { result } = renderHook(() => useExecutionFilters(), {
      wrapper: createWrapper(['/?status=COMPLETED&environment=prod']),
    });
    expect(result.current.filters.status).toBe('COMPLETED');
    expect(result.current.filters.environment).toBe('prod');
    expect(result.current.activeFilterCount).toBe(2);
    expect(result.current.hasActiveFilters).toBe(true);
  });

  it('parses action_id from URL', () => {
    const { result } = renderHook(() => useExecutionFilters(), {
      wrapper: createWrapper(['/?action_id=42']),
    });
    expect(result.current.filters.action_id).toBe(42);
    expect(result.current.activeFilterCount).toBe(1);
  });

  it('parses tags from URL as array', () => {
    const { result } = renderHook(() => useExecutionFilters(), {
      wrapper: createWrapper(['/?tags=tag1,tag2,tag3']),
    });
    expect(result.current.filters.tags).toEqual(['tag1', 'tag2', 'tag3']);
    expect(result.current.activeFilterCount).toBe(1);
  });

  it('parses date range from URL', () => {
    const { result } = renderHook(() => useExecutionFilters(), {
      wrapper: createWrapper(['/?start_date=2025-01-01&end_date=2025-01-31']),
    });
    expect(result.current.filters.start_date).toBe('2025-01-01');
    expect(result.current.filters.end_date).toBe('2025-01-31');
    expect(result.current.activeFilterCount).toBe(1); // start/end count as 1
  });

  it('parses engine filter from URL', () => {
    const { result } = renderHook(() => useExecutionFilters(), {
      wrapper: createWrapper(['/?engine=aap']),
    });
    expect(result.current.filters.engine).toBe('aap');
    expect(result.current.activeFilterCount).toBe(1);
  });

  it('applyFilters updates filters and navigates', () => {
    const { result } = renderHook(() => useExecutionFilters(), {
      wrapper: createWrapper(['/']),
    });

    act(() => {
      result.current.applyFilters({
        status: 'RUNNING',
        environment: 'dev',
        action_id: null,
        engine: null,
        tags: null,
        start_date: null,
        end_date: null,
      });
    });

    expect(result.current.filters.status).toBe('RUNNING');
    expect(result.current.filters.environment).toBe('dev');
  });

  it('resetFilters clears all filters', () => {
    const { result } = renderHook(() => useExecutionFilters(), {
      wrapper: createWrapper(['/?status=COMPLETED&environment=prod']),
    });

    act(() => {
      result.current.resetFilters();
    });

    expect(result.current.filters.status).toBeNull();
    expect(result.current.filters.environment).toBeNull();
    expect(result.current.activeFilterCount).toBe(0);
  });

  it('applyFilters with tags builds URL correctly', () => {
    const { result } = renderHook(() => useExecutionFilters(), {
      wrapper: createWrapper(['/']),
    });

    act(() => {
      result.current.applyFilters({
        status: null,
        environment: null,
        action_id: null,
        engine: 'aap',
        tags: ['tag1', 'tag2'],
        start_date: null,
        end_date: null,
      });
    });

    expect(result.current.filters.tags).toEqual(['tag1', 'tag2']);
    expect(result.current.filters.engine).toBe('aap');
  });

  it('counts multiple active filters', () => {
    const { result } = renderHook(() => useExecutionFilters(), {
      wrapper: createWrapper(['/?status=COMPLETED&environment=prod&engine=aap']),
    });
    expect(result.current.activeFilterCount).toBe(3);
  });

  it('applyFilters with action_id', () => {
    const { result } = renderHook(() => useExecutionFilters(), {
      wrapper: createWrapper(['/']),
    });

    act(() => {
      result.current.applyFilters({
        status: null,
        environment: null,
        action_id: 5,
        engine: null,
        tags: null,
        start_date: '2025-01-01',
        end_date: '2025-01-31',
      });
    });

    expect(result.current.filters.action_id).toBe(5);
    expect(result.current.filters.start_date).toBe('2025-01-01');
  });
});

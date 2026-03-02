/**
 * Tests for useCalendarFilters hook — coverage.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import React from 'react';
import { MemoryRouter } from 'react-router';
import { useCalendarFilters } from './useCalendarFilters';

// Wrapper with MemoryRouter (required for useNavigate + useLocation)
const wrapper = ({ children }: { children: React.ReactNode }) =>
  React.createElement(MemoryRouter, { initialEntries: ['/'] }, children);

// Wrapper with initial search params
function makeWrapper(search: string) {
  return ({ children }: { children: React.ReactNode }) =>
    React.createElement(MemoryRouter, { initialEntries: [`/${search}`] }, children);
}

describe('useCalendarFilters — coverage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('initial state: all filters null, activeFilterCount=0, hasActiveFilters=false', () => {
    const { result } = renderHook(() => useCalendarFilters(), { wrapper });
    expect(result.current.filters.action_id).toBeNull();
    expect(result.current.filters.environment).toBeNull();
    expect(result.current.filters.engine).toBeNull();
    expect(result.current.filters.platform).toBeNull();
    expect(result.current.filters.start_date).toBeNull();
    expect(result.current.filters.end_date).toBeNull();
    expect(result.current.activeFilterCount).toBe(0);
    expect(result.current.hasActiveFilters).toBe(false);
  });

  it('applyFilters updates filters and hasActiveFilters', () => {
    const { result } = renderHook(() => useCalendarFilters(), { wrapper });
    act(() => {
      result.current.applyFilters({ action_id: 5, environment: 'dev' as never, engine: null, platform: null, start_date: null, end_date: null });
    });
    expect(result.current.filters.action_id).toBe(5);
    expect(result.current.filters.environment).toBe('dev');
    expect(result.current.hasActiveFilters).toBe(true);
    expect(result.current.activeFilterCount).toBe(2);
  });

  it('resetFilters clears all filters', () => {
    const { result } = renderHook(() => useCalendarFilters(), { wrapper });
    act(() => {
      result.current.applyFilters({ action_id: 5, environment: 'prod' as never, engine: 'AAP', platform: 'ansible', start_date: '2026-01-01', end_date: '2026-01-31' });
    });
    expect(result.current.activeFilterCount).toBeGreaterThan(0);
    act(() => { result.current.resetFilters(); });
    expect(result.current.activeFilterCount).toBe(0);
    expect(result.current.hasActiveFilters).toBe(false);
  });

  it('parses filters from URL on mount', () => {
    const w = makeWrapper('?action_id=3&environment=prod&engine=AAP');
    const { result } = renderHook(() => useCalendarFilters(), { wrapper: w });
    expect(result.current.filters.action_id).toBe(3);
    expect(result.current.filters.environment).toBe('prod');
    expect(result.current.filters.engine).toBe('AAP');
  });

  it('activeFilterCount counts date range as 1', () => {
    const { result } = renderHook(() => useCalendarFilters(), { wrapper });
    act(() => {
      result.current.applyFilters({ action_id: null, environment: null, engine: null, platform: null, start_date: '2026-01-01', end_date: null });
    });
    expect(result.current.activeFilterCount).toBe(1);
  });

  it('invalid action_id in URL is treated as null', () => {
    const w = makeWrapper('?action_id=not-a-number');
    const { result } = renderHook(() => useCalendarFilters(), { wrapper: w });
    expect(result.current.filters.action_id).toBeNull();
  });
});

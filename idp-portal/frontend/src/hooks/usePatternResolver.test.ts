import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { usePatternResolver } from './usePatternResolver';
import { fetchInventoryTargets } from '../services/execution_service';

vi.mock('../services/execution_service', () => ({
  submitExecution: vi.fn(),
  fetchInventoryItems: vi.fn().mockResolvedValue([]),
  fetchInventoryTargets: vi.fn().mockResolvedValue([]),
}));

const mockTargets = [
  { name: 'db-prod-01', environment: 'prod', target_type: 'server', metadata: null },
  { name: 'db-prod-02', environment: 'prod', target_type: 'server', metadata: null },
  { name: 'db-dev-01', environment: 'dev', target_type: 'server', metadata: null },
  { name: 'srv-dev-01', environment: 'dev', target_type: 'server', metadata: null },
  { name: 'srv-prod-01', environment: 'prod', target_type: 'server', metadata: null },
];

// Use a very short debounce for tests (real timers)
const TEST_DEBOUNCE = 50;

describe('usePatternResolver', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(fetchInventoryTargets).mockResolvedValue(mockTargets);
  });

  it('returns empty targets when not enabled', () => {
    const { result } = renderHook(() =>
      usePatternResolver({
        enabled: false,
        inputMode: 'pattern',
        pattern: 'db-*',
        debounceMs: TEST_DEBOUNCE,
      })
    );

    expect(result.current.resolvedTargets).toEqual([]);
    expect(result.current.isResolving).toBe(false);
  });

  it('returns empty targets when inputMode is not pattern', () => {
    const { result } = renderHook(() =>
      usePatternResolver({
        enabled: true,
        inputMode: 'list',
        pattern: 'db-*',
        debounceMs: TEST_DEBOUNCE,
      })
    );

    expect(result.current.resolvedTargets).toEqual([]);
    expect(result.current.isResolving).toBe(false);
  });

  it('returns empty targets when pattern is empty', () => {
    const { result } = renderHook(() =>
      usePatternResolver({
        enabled: true,
        inputMode: 'pattern',
        pattern: '',
        debounceMs: TEST_DEBOUNCE,
      })
    );

    expect(result.current.resolvedTargets).toEqual([]);
    expect(result.current.isResolving).toBe(false);
  });

  it('resolves targets with glob pattern db-prod-*', async () => {
    const { result } = renderHook(() =>
      usePatternResolver({
        enabled: true,
        inputMode: 'pattern',
        pattern: 'db-prod-*',
        debounceMs: TEST_DEBOUNCE,
      })
    );

    await waitFor(() => {
      expect(result.current.resolvedTargets).toEqual([
        { name: 'db-prod-01', environment: 'prod' },
        { name: 'db-prod-02', environment: 'prod' },
      ]);
    });

    expect(fetchInventoryTargets).toHaveBeenCalledTimes(1);
  });

  it('resolves all db targets with wildcard db-*', async () => {
    const { result } = renderHook(() =>
      usePatternResolver({
        enabled: true,
        inputMode: 'pattern',
        pattern: 'db-*',
        debounceMs: TEST_DEBOUNCE,
      })
    );

    await waitFor(() => {
      expect(result.current.resolvedTargets).toHaveLength(3);
      expect(result.current.resolvedTargets.map((t) => t.name)).toEqual([
        'db-prod-01',
        'db-prod-02',
        'db-dev-01',
      ]);
    });
  });

  it('returns empty array when no targets match pattern', async () => {
    const { result } = renderHook(() =>
      usePatternResolver({
        enabled: true,
        inputMode: 'pattern',
        pattern: 'nonexistent-*',
        debounceMs: TEST_DEBOUNCE,
      })
    );

    await waitFor(() => {
      expect(fetchInventoryTargets).toHaveBeenCalledTimes(1);
    });

    expect(result.current.resolvedTargets).toEqual([]);
  });

  it('handles fetch error gracefully', async () => {
    vi.mocked(fetchInventoryTargets).mockRejectedValue(new Error('Network error'));

    const { result } = renderHook(() =>
      usePatternResolver({
        enabled: true,
        inputMode: 'pattern',
        pattern: 'db-*',
        debounceMs: TEST_DEBOUNCE,
      })
    );

    await waitFor(() => {
      expect(result.current.isResolving).toBe(false);
    });

    expect(result.current.resolvedTargets).toEqual([]);
  });

  it('clears resolved targets when switching away from pattern mode', async () => {
    const { result, rerender } = renderHook(
      ({ inputMode }: { inputMode: string }) =>
        usePatternResolver({
          enabled: true,
          inputMode,
          pattern: 'db-*',
          debounceMs: TEST_DEBOUNCE,
        }),
      { initialProps: { inputMode: 'pattern' } }
    );

    // Wait for resolution
    await waitFor(() => {
      expect(result.current.resolvedTargets).toHaveLength(3);
    });

    // Switch to list mode
    rerender({ inputMode: 'list' });

    await waitFor(() => {
      expect(result.current.resolvedTargets).toEqual([]);
    });
  });
});

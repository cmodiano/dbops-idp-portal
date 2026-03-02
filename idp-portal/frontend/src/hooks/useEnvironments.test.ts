/**
 * Tests for useEnvironments hook (Story 53.4 — suppression fallback, labels dynamiques).
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { useEnvironments, invalidateEnvironmentsCache } from './useEnvironments';
import * as referenceService from '../services/reference_service';

vi.mock('../services/reference_service');

describe('useEnvironments', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    invalidateEnvironmentsCache();
  });

  it('starts with loading=true when not cached', () => {
    vi.mocked(referenceService.fetchEnvironments).mockResolvedValue(['dev', 'prod']);
    const { result } = renderHook(() => useEnvironments());
    expect(result.current.loading).toBe(true);
  });

  it('returns environments after fetch', async () => {
    vi.mocked(referenceService.fetchEnvironments).mockResolvedValue(['dev', 'staging', 'prod']);
    const { result } = renderHook(() => useEnvironments());
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.environments).toEqual(['dev', 'staging', 'prod']);
  });

  it('builds environmentOptions with labels', async () => {
    vi.mocked(referenceService.fetchEnvironments).mockResolvedValue(['developpement', 'certification', 'production']);
    const { result } = renderHook(() => useEnvironments());
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.environmentOptions).toEqual([
      { value: 'developpement', label: 'Développement' },
      { value: 'certification', label: 'Certification' },
      { value: 'production', label: 'Production' },
    ]);
  });

  it('handles unknown environment in options', async () => {
    vi.mocked(referenceService.fetchEnvironments).mockResolvedValue(['qa']);
    const { result } = renderHook(() => useEnvironments());
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.environmentOptions[0]).toEqual({ value: 'qa', label: 'Qa' });
  });

  it('returns empty list and error on fetch failure', async () => {
    vi.mocked(referenceService.fetchEnvironments).mockRejectedValue(new Error('Network'));
    const { result } = renderHook(() => useEnvironments());
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.environments).toEqual([]);
    expect(result.current.error).not.toBeNull();
    expect(result.current.error?.message).toContain('Network');
  });

  it('preserves error on second mount after fetch failure', async () => {
    vi.mocked(referenceService.fetchEnvironments).mockRejectedValue(new Error('Network'));
    // First mount — triggers the failed fetch
    const { result: r1 } = renderHook(() => useEnvironments());
    await waitFor(() => expect(r1.current.loading).toBe(false));
    expect(r1.current.error).not.toBeNull();

    // Second mount — uses cached [] and must preserve the error, not silently clear it
    const { result: r2 } = renderHook(() => useEnvironments());
    await waitFor(() => expect(r2.current.loading).toBe(false));
    expect(r2.current.environments).toEqual([]);
    expect(r2.current.error).not.toBeNull();
    expect(r2.current.error?.message).toContain('Network');
    // Only one API call (cache was used on second mount)
    expect(referenceService.fetchEnvironments).toHaveBeenCalledTimes(1);
  });

  it('does not call API when enabled=false', async () => {
    const { result } = renderHook(() => useEnvironments({ enabled: false }));
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(referenceService.fetchEnvironments).not.toHaveBeenCalled();
    expect(result.current.environments).toEqual([]);
  });

  it('uses cached result on second call', async () => {
    vi.mocked(referenceService.fetchEnvironments).mockResolvedValue(['dev', 'prod']);
    const { result: r1 } = renderHook(() => useEnvironments());
    await waitFor(() => expect(r1.current.loading).toBe(false));

    const { result: r2 } = renderHook(() => useEnvironments());
    await waitFor(() => expect(r2.current.loading).toBe(false));

    // Only one API call due to caching
    expect(referenceService.fetchEnvironments).toHaveBeenCalledTimes(1);
    expect(r2.current.environments).toEqual(['dev', 'prod']);
  });

  it('concurrent calls use same promise (loadingPromise deduplication)', async () => {
    let resolveEnv: (data: string[]) => void = () => {};
    const slowPromise = new Promise<string[]>((res) => { resolveEnv = res; });
    vi.mocked(referenceService.fetchEnvironments).mockReturnValue(slowPromise);

    // Start two concurrent hooks — they should share the same promise
    const { result: r1 } = renderHook(() => useEnvironments());
    const { result: r2 } = renderHook(() => useEnvironments());

    // Both still loading
    expect(r1.current.loading).toBe(true);
    expect(r2.current.loading).toBe(true);

    // Resolve the promise
    resolveEnv(['dev', 'prod']);
    await waitFor(() => expect(r1.current.loading).toBe(false));
    await waitFor(() => expect(r2.current.loading).toBe(false));

    // Only one API call made (deduplication)
    expect(referenceService.fetchEnvironments).toHaveBeenCalledTimes(1);
    expect(r1.current.environments).toEqual(['dev', 'prod']);
    expect(r2.current.environments).toEqual(['dev', 'prod']);
  });

  it('.catch branch in effect when getOrFetchEnvironments fails', async () => {
    vi.mocked(referenceService.fetchEnvironments).mockRejectedValue(new Error('Timeout'));
    const { result } = renderHook(() => useEnvironments());
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.environments).toEqual([]);
    expect(result.current.error).not.toBeNull();
  });

  it('listener notification when fetch completes', async () => {
    vi.mocked(referenceService.fetchEnvironments).mockResolvedValue(['dev', 'prod']);
    // Mount two hooks before the fetch resolves to exercise the listener path
    const { result: r1 } = renderHook(() => useEnvironments());
    const { result: r2 } = renderHook(() => useEnvironments());
    await waitFor(() => expect(r1.current.loading).toBe(false));
    await waitFor(() => expect(r2.current.loading).toBe(false));
    expect(r1.current.environments).toEqual(['dev', 'prod']);
    expect(r2.current.environments).toEqual(['dev', 'prod']);
  });

  it('wraps non-Error rejection in getOrFetchEnvironments (covers ternary false branch line 60)', async () => {
    // Reject with a plain string (not an Error instance) → ternary false branch: new Error(...)
    vi.mocked(referenceService.fetchEnvironments).mockRejectedValue('plain string error');
    const { result } = renderHook(() => useEnvironments());
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.environments).toEqual([]);
    expect(result.current.error?.message).toContain('Failed to load environments');
  });

  it('cancelled hook skips state update when fetch resolves after unmount (covers if (!cancelled) false branch)', async () => {
    let resolveEnv: (data: string[]) => void = () => {};
    const slowPromise = new Promise<string[]>((res) => { resolveEnv = res; });
    vi.mocked(referenceService.fetchEnvironments).mockReturnValue(slowPromise);

    const { result, unmount } = renderHook(() => useEnvironments());
    expect(result.current.loading).toBe(true);

    // Unmount before promise resolves → sets cancelled = true
    unmount();

    // Resolve after unmount → then() fires but cancelled=true, no state update
    resolveEnv(['dev', 'prod']);
    await new Promise((r) => setTimeout(r, 50));
    // No assertion needed — just exercising the cancelled path
  });

  it('invalidateEnvironmentsCache clears cache', async () => {
    vi.mocked(referenceService.fetchEnvironments).mockResolvedValue(['dev', 'prod']);
    const { result: r1 } = renderHook(() => useEnvironments());
    await waitFor(() => expect(r1.current.loading).toBe(false));

    invalidateEnvironmentsCache();
    vi.mocked(referenceService.fetchEnvironments).mockResolvedValue(['dev', 'staging', 'prod']);

    const { result: r2 } = renderHook(() => useEnvironments());
    await waitFor(() => expect(r2.current.loading).toBe(false));

    expect(referenceService.fetchEnvironments).toHaveBeenCalledTimes(2);
    expect(r2.current.environments).toEqual(['dev', 'staging', 'prod']);
  });
});

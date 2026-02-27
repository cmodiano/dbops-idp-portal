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

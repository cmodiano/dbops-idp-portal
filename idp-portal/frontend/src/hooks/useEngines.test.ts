/**
 * Tests for useEngines hook — coverage.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { useEngines, invalidateEnginesCache } from './useEngines';
import * as referenceService from '../services/reference_service';
import type { RefEngine } from '../services/reference_service';

vi.mock('../services/reference_service');

const mockFetchEngines = vi.mocked(referenceService.fetchEngines);

const mockEngines: RefEngine[] = [
  { id: 1, code: 'AAP', label: 'Ansible Automation Platform', is_active: 1, display_order: 1, icon_url: null },
  { id: 2, code: 'Terraform', label: 'Terraform', is_active: 1, display_order: 2, icon_url: null },
  { id: 3, code: 'Legacy', label: 'Legacy Engine', is_active: 0, display_order: 3, icon_url: null },
];

describe('useEngines', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    invalidateEnginesCache();
  });

  it('initial state: loading=true when not cached', () => {
    mockFetchEngines.mockResolvedValue(mockEngines);
    const { result } = renderHook(() => useEngines());
    expect(result.current.loading).toBe(true);
  });

  it('returns engines after successful fetch', async () => {
    mockFetchEngines.mockResolvedValue(mockEngines);
    const { result } = renderHook(() => useEngines());
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.engines).toEqual(mockEngines);
    expect(result.current.error).toBeNull();
  });

  it('error handling on fetch failure', async () => {
    mockFetchEngines.mockRejectedValue(new Error('Network error'));
    const { result } = renderHook(() => useEngines());
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.error).not.toBeNull();
    expect(result.current.error?.message).toContain('Network error');
  });

  it('uses cached result on second call (deduplication)', async () => {
    mockFetchEngines.mockResolvedValue(mockEngines);
    const { result: r1 } = renderHook(() => useEngines());
    await waitFor(() => expect(r1.current.loading).toBe(false));

    const { result: r2 } = renderHook(() => useEngines());
    await waitFor(() => expect(r2.current.loading).toBe(false));

    expect(mockFetchEngines).toHaveBeenCalledTimes(1);
    expect(r2.current.engines).toEqual(mockEngines);
  });

  it('engineOptions filtered by is_active and sorted by display_order', async () => {
    mockFetchEngines.mockResolvedValue(mockEngines);
    const { result } = renderHook(() => useEngines());
    await waitFor(() => expect(result.current.loading).toBe(false));

    // Only active engines (is_active=1) appear, sorted by display_order
    expect(result.current.engineOptions).toHaveLength(2);
    expect(result.current.engineOptions[0].value).toBe('AAP');
    expect(result.current.engineOptions[1].value).toBe('Terraform');
  });

  it('invalidateEnginesCache clears cache', async () => {
    mockFetchEngines.mockResolvedValue(mockEngines);
    const { result: r1 } = renderHook(() => useEngines());
    await waitFor(() => expect(r1.current.loading).toBe(false));

    invalidateEnginesCache();
    const newEngines: RefEngine[] = [{ id: 4, code: 'New', label: 'New Engine', is_active: 1, display_order: 1, icon_url: null }];
    mockFetchEngines.mockResolvedValue(newEngines);

    const { result: r2 } = renderHook(() => useEngines());
    await waitFor(() => expect(r2.current.loading).toBe(false));

    expect(mockFetchEngines).toHaveBeenCalledTimes(2);
    expect(r2.current.engines).toEqual(newEngines);
  });

  it('concurrent calls use same promise (loadingPromise deduplication)', async () => {
    let resolveEngines: (data: RefEngine[]) => void = () => {};
    const slowPromise = new Promise<RefEngine[]>((res) => { resolveEngines = res; });
    mockFetchEngines.mockReturnValue(slowPromise);

    const { result: r1 } = renderHook(() => useEngines());
    const { result: r2 } = renderHook(() => useEngines());

    expect(r1.current.loading).toBe(true);
    expect(r2.current.loading).toBe(true);

    resolveEngines(mockEngines);
    await waitFor(() => expect(r1.current.loading).toBe(false));
    await waitFor(() => expect(r2.current.loading).toBe(false));

    expect(mockFetchEngines).toHaveBeenCalledTimes(1);
  });
});

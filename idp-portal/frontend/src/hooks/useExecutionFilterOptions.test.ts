/**
 * Tests for useExecutionFilterOptions hook (Story 71.11, AC #4).
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, act, waitFor } from '@testing-library/react';
import { useExecutionFilterOptions } from './useExecutionFilterOptions';
import * as executionService from '../services/execution_service';
import * as catalogService from '../services/catalog_service';

vi.mock('../services/execution_service', () => ({
  fetchExecutionTags: vi.fn(),
}));

vi.mock('../services/catalog_service', () => ({
  fetchCatalogActions: vi.fn(),
}));

describe('useExecutionFilterOptions', () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  it('pendant le chargement — loading=true, tags=[], actions=[]', async () => {
    let resolveTagsFn!: (v: string[]) => void;
    let resolveActionsFn!: (v: any[]) => void;
    vi.mocked(executionService.fetchExecutionTags).mockReturnValue(
      new Promise(r => { resolveTagsFn = r; }),
    );
    vi.mocked(catalogService.fetchCatalogActions).mockReturnValue(
      new Promise(r => { resolveActionsFn = r; }),
    );

    const { result } = renderHook(() => useExecutionFilterOptions());

    // Wait for useEffect to fire and set loading=true
    await waitFor(() => {
      expect(result.current.loading).toBe(true);
    });
    expect(result.current.tags).toEqual([]);
    expect(result.current.actions).toEqual([]);

    // Cleanup: resolve promises to avoid act() warning
    act(() => {
      resolveTagsFn([]);
      resolveActionsFn([]);
    });
  });

  it('chargement réussi — tags et actions populés, loading=false', async () => {
    const mockTags = ['tag1', 'tag2'];
    const mockActions = [{ id: 1, name: 'Deploy' }] as any;
    vi.mocked(executionService.fetchExecutionTags).mockResolvedValue(mockTags);
    vi.mocked(catalogService.fetchCatalogActions).mockResolvedValue(mockActions);

    const { result } = renderHook(() => useExecutionFilterOptions());

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.tags).toEqual(mockTags);
    expect(result.current.actions).toEqual(mockActions);
  });

  it('fetchExecutionTags rejette — tags=[] (fallback via .catch(() => []))', async () => {
    vi.mocked(executionService.fetchExecutionTags).mockRejectedValue(new Error('Network Error'));
    vi.mocked(catalogService.fetchCatalogActions).mockResolvedValue([]);

    const { result } = renderHook(() => useExecutionFilterOptions());

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.tags).toEqual([]);
  });

  it('fetchCatalogActions rejette — actions=[] (fallback)', async () => {
    vi.mocked(executionService.fetchExecutionTags).mockResolvedValue(['tag1']);
    vi.mocked(catalogService.fetchCatalogActions).mockRejectedValue(new Error('API Error'));

    const { result } = renderHook(() => useExecutionFilterOptions());

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.actions).toEqual([]);
    expect(result.current.tags).toEqual(['tag1']);
  });
});

/**
 * Tests for useInventorySchema hook — Story 62.5.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, waitFor, act } from '@testing-library/react';
import { useInventorySchema } from './useInventorySchema';

vi.mock('../services/execution_service', () => ({
  fetchInventorySchema: vi.fn(),
}));

import { fetchInventorySchema } from '../services/execution_service';
const mockFetchSchema = fetchInventorySchema as ReturnType<typeof vi.fn>;

const CACHE_KEY = 'inventory_schema_cache';

const MOCK_SCHEMA = {
  servers: ['id', 'name', 'environment', 'region'],
  instances: ['id', 'name', 'server_ref'],
  databases: ['id', 'name'],
};

describe('useInventorySchema', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    sessionStorage.clear();
  });

  afterEach(() => {
    sessionStorage.clear();
  });

  it('returns schema on successful fetch', async () => {
    mockFetchSchema.mockResolvedValue(MOCK_SCHEMA);

    const { result } = renderHook(() => useInventorySchema());

    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.schema).toEqual(MOCK_SCHEMA);
    expect(result.current.error).toBeNull();
    expect(mockFetchSchema).toHaveBeenCalledOnce();
  });

  it('sets error when fetch fails', async () => {
    mockFetchSchema.mockRejectedValue(new Error('Network error'));

    const { result } = renderHook(() => useInventorySchema());

    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.schema).toBeNull();
    expect(result.current.error).toBe('Network error');
  });

  it('uses valid sessionStorage cache without network call', async () => {
    sessionStorage.setItem(
      CACHE_KEY,
      JSON.stringify({ data: MOCK_SCHEMA, timestamp: Date.now() }),
    );

    const { result } = renderHook(() => useInventorySchema());

    // Cache hit is synchronous — loading should be false immediately
    expect(result.current.loading).toBe(false);
    expect(result.current.schema).toEqual(MOCK_SCHEMA);
    expect(mockFetchSchema).not.toHaveBeenCalled();
  });

  it('ignores expired sessionStorage cache and fetches from network', async () => {
    sessionStorage.setItem(
      CACHE_KEY,
      JSON.stringify({
        data: MOCK_SCHEMA,
        timestamp: Date.now() - 6 * 60 * 1000, // 6 minutes — expired
      }),
    );
    mockFetchSchema.mockResolvedValue(MOCK_SCHEMA);

    const { result } = renderHook(() => useInventorySchema());

    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(mockFetchSchema).toHaveBeenCalledOnce();
    expect(result.current.schema).toEqual(MOCK_SCHEMA);
  });

  it('does not update state after unmount (cancelled flag)', async () => {
    let resolveSchema!: (value: typeof MOCK_SCHEMA) => void;
    const pendingPromise = new Promise<typeof MOCK_SCHEMA>((resolve) => {
      resolveSchema = resolve;
    });
    mockFetchSchema.mockReturnValue(pendingPromise);

    const { result, unmount } = renderHook(() => useInventorySchema());

    // Still loading — unmount before promise resolves
    expect(result.current.loading).toBe(true);
    unmount();

    // Resolve after unmount — cancelled flag must prevent state updates
    await act(async () => {
      resolveSchema(MOCK_SCHEMA);
      await pendingPromise;
    });

    // Schema and loading must remain at their initial (pre-unmount) values,
    // proving that setSchema/setLoading were NOT called after unmount.
    expect(result.current.schema).toBeNull();
    expect(result.current.loading).toBe(true);
    expect(mockFetchSchema).toHaveBeenCalledOnce();
  });
});

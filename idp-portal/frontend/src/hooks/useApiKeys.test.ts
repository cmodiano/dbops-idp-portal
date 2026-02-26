import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, waitFor, act } from '@testing-library/react';

import { useApiKeys } from './useApiKeys';
import {
  createApiKey,
  listApiKeys,
  revokeApiKey,
  type ApiKeyListItem,
} from '../services/api_keys_service';

vi.mock('../services/api_keys_service', () => ({
  listApiKeys: vi.fn(),
  createApiKey: vi.fn(),
  revokeApiKey: vi.fn(),
}));

const mockListApiKeys = listApiKeys as ReturnType<typeof vi.fn>;
const mockCreateApiKey = createApiKey as ReturnType<typeof vi.fn>;
const mockRevokeApiKey = revokeApiKey as ReturnType<typeof vi.fn>;

describe('useApiKeys', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('loads API keys on mount', async () => {
    const items: ApiKeyListItem[] = [
      {
        id: 1,
        name: 'CI Key',
        scope: 'executions',
        created_at: '2026-02-26T10:00:00Z',
        expires_at: null,
        is_active: true,
        status: 'active',
      },
    ];
    mockListApiKeys.mockResolvedValue(items);

    const { result } = renderHook(() => useApiKeys());

    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.keys).toEqual(items);
    expect(result.current.error).toBeNull();
  });

  it('creates a key and exposes raw_key once', async () => {
    mockListApiKeys.mockResolvedValue([]);
    mockCreateApiKey.mockResolvedValue({
      id: 10,
      name: 'Script Key',
      scope: 'catalog',
      created_at: '2026-02-26T11:00:00Z',
      raw_key: 'raw-secret',
    });
    mockListApiKeys.mockResolvedValueOnce([]).mockResolvedValueOnce([
      {
        id: 10,
        name: 'Script Key',
        scope: 'catalog',
        created_at: '2026-02-26T11:00:00Z',
        expires_at: null,
        is_active: true,
        status: 'active',
      },
    ]);

    const { result } = renderHook(() => useApiKeys());
    await waitFor(() => expect(result.current.loading).toBe(false));

    await act(async () => {
      await result.current.create('Script Key', 'catalog');
    });

    expect(mockCreateApiKey).toHaveBeenCalledWith({ name: 'Script Key', scope: 'catalog' });
    expect(result.current.lastCreatedRawKey).toBe('raw-secret');
    expect(result.current.keys).toHaveLength(1);
  });

  it('propagates 429 API_KEY_LIMIT_REACHED error with backend message', async () => {
    mockListApiKeys.mockResolvedValue([]);
    mockCreateApiKey.mockRejectedValue(new Error('Limite de 5 clés API actives atteinte'));

    const { result } = renderHook(() => useApiKeys());
    await waitFor(() => expect(result.current.loading).toBe(false));

    await act(async () => {
      try {
        await result.current.create('Extra Key', 'full');
      } catch {
        // Expected to throw
      }
    });

    expect(result.current.error).toBe('Limite de 5 clés API actives atteinte');
    expect(result.current.lastCreatedRawKey).toBeNull();
  });

  it('revokes key then refreshes list', async () => {
    mockListApiKeys
      .mockResolvedValueOnce([
        {
          id: 1,
          name: 'Old Key',
          scope: 'full',
          created_at: '2026-02-26T08:00:00Z',
          expires_at: null,
          is_active: true,
          status: 'active',
        },
      ])
      .mockResolvedValueOnce([]);
    mockRevokeApiKey.mockResolvedValue(undefined);

    const { result } = renderHook(() => useApiKeys());
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.keys).toHaveLength(1);

    await act(async () => {
      await result.current.revoke(1);
    });

    expect(mockRevokeApiKey).toHaveBeenCalledWith(1);
    expect(result.current.keys).toHaveLength(0);
  });
});

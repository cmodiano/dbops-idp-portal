/**
 * Tests for useServiceNowIntegrations hook — Story 31.6.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { useServiceNowIntegrations } from './useServiceNowIntegrations';

vi.mock('../services/integrations_service', () => ({
  getIntegrationsByType: vi.fn(),
}));

import { getIntegrationsByType } from '../services/integrations_service';
const mockGetIntegrations = getIntegrationsByType as ReturnType<typeof vi.fn>;

const CACHE_KEY = 'sn_integrations';

describe('useServiceNowIntegrations', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    sessionStorage.clear();
  });

  afterEach(() => {
    sessionStorage.clear();
  });

  it('filters out status=invalid integrations, keeps active ones', async () => {
    // API already returns only servicenow type (via ?type=servicenow), hook filters invalid status
    mockGetIntegrations.mockResolvedValue([
      { id: 1, name: 'SN Prod', type: 'servicenow', status: 'active' },
      { id: 3, name: 'SN Dev', type: 'servicenow', status: 'invalid' },
      { id: 4, name: 'SN Staging', type: 'servicenow', status: 'active' },
    ]);

    const { result } = renderHook(() => useServiceNowIntegrations());

    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.integrations).toHaveLength(2);
    expect(result.current.integrations.map((i) => i.id)).toEqual([1, 4]);
    expect(result.current.error).toBeNull();
    // Verify API was called with the type filter
    expect(mockGetIntegrations).toHaveBeenCalledWith('servicenow');
  });

  it('returns integrationOptions with value/label', async () => {
    mockGetIntegrations.mockResolvedValue([
      { id: 1, name: 'SN Prod', type: 'servicenow', status: 'active' },
    ]);

    const { result } = renderHook(() => useServiceNowIntegrations());

    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.integrationOptions).toEqual([
      { value: 1, label: 'SN Prod (servicenow)' },
    ]);
  });

  it('uses sessionStorage cache when valid', async () => {
    const cached = {
      data: [{ id: 5, name: 'Cached SN', type: 'servicenow', status: 'active' }],
      timestamp: Date.now(),
    };
    sessionStorage.setItem(CACHE_KEY, JSON.stringify(cached));

    const { result } = renderHook(() => useServiceNowIntegrations());

    // Should use cache immediately, no API call
    expect(result.current.loading).toBe(false);
    expect(result.current.integrations).toHaveLength(1);
    expect(result.current.integrations[0].name).toBe('Cached SN');
    expect(mockGetIntegrations).not.toHaveBeenCalled();
  });

  it('ignores expired cache and fetches from API', async () => {
    const expired = {
      data: [{ id: 5, name: 'Old SN', type: 'servicenow', status: 'active' }],
      timestamp: Date.now() - 6 * 60 * 1000, // 6 minutes ago
    };
    sessionStorage.setItem(CACHE_KEY, JSON.stringify(expired));

    mockGetIntegrations.mockResolvedValue([
      { id: 1, name: 'Fresh SN', type: 'servicenow', status: 'active' },
    ]);

    const { result } = renderHook(() => useServiceNowIntegrations());

    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.integrations[0].name).toBe('Fresh SN');
    expect(mockGetIntegrations).toHaveBeenCalledOnce();
  });

  it('sets error on fetch failure', async () => {
    mockGetIntegrations.mockRejectedValue(new Error('Network error'));

    const { result } = renderHook(() => useServiceNowIntegrations());

    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.error).toBe('Network error');
    expect(result.current.integrations).toEqual([]);
  });
});

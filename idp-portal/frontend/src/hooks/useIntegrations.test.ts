/**
 * Tests for useIntegrations hook — coverage.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { useIntegrations } from './useIntegrations';

vi.mock('../services/integrations_service', () => ({
  getIntegrations: vi.fn(),
}));

import { getIntegrations } from '../services/integrations_service';
const mockGetIntegrations = vi.mocked(getIntegrations);

describe('useIntegrations — coverage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('initial state: loading=true', () => {
    mockGetIntegrations.mockResolvedValue([]);
    const { result } = renderHook(() => useIntegrations());
    expect(result.current.loading).toBe(true);
  });

  it('returns integrations after successful fetch', async () => {
    const mockData = [{ id: 1, name: 'SN Prod', type: 'servicenow', status: 'active' }];
    mockGetIntegrations.mockResolvedValue(mockData as never);
    const { result } = renderHook(() => useIntegrations());
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.integrations).toEqual(mockData);
    expect(result.current.error).toBeNull();
  });

  it('error handling on fetch failure', async () => {
    mockGetIntegrations.mockRejectedValue(new Error('Network error'));
    const { result } = renderHook(() => useIntegrations());
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.integrations).toEqual([]);
    expect(result.current.error).toBe('Network error');
  });
});

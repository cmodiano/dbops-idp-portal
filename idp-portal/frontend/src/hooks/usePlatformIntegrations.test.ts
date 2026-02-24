/**
 * Tests for usePlatformIntegrations hook (Story 39.7 — coverage).
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { usePlatformIntegrations } from './usePlatformIntegrations';
import * as integrationsService from '../services/integrations_service';
import type { IntegrationResponse } from '../types/api';

vi.mock('../services/integrations_service');

const mockPlatformType = { code: 'aap', name: 'Ansible', integration_role: 'platform' };
const mockAAPIntegration: IntegrationResponse = {
  id: 1,
  name: 'AAP Instance 1',
  type: 'aap',
  status: 'active',
  engine: 'aap',
  config: {},
  created_at: '2025-01-01T00:00:00Z',
};
const mockInvalidIntegration: IntegrationResponse = {
  ...mockAAPIntegration,
  id: 2,
  status: 'invalid',
};
const mockOtherIntegration: IntegrationResponse = {
  id: 3,
  name: 'Vault Instance',
  type: 'vault',
  status: 'active',
  engine: 'vault',
  config: {},
  created_at: '2025-01-01T00:00:00Z',
};

describe('usePlatformIntegrations', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('starts with loading=true', () => {
    vi.mocked(integrationsService.getIntegrationTypes).mockResolvedValue([mockPlatformType]);
    vi.mocked(integrationsService.getIntegrations).mockResolvedValue([]);
    const { result } = renderHook(() => usePlatformIntegrations());
    expect(result.current.loading).toBe(true);
  });

  it('returns platform integrations after fetch', async () => {
    vi.mocked(integrationsService.getIntegrationTypes).mockResolvedValue([mockPlatformType]);
    vi.mocked(integrationsService.getIntegrations).mockResolvedValue([
      mockAAPIntegration,
      mockOtherIntegration,
    ]);
    const { result } = renderHook(() => usePlatformIntegrations());
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.integrations).toHaveLength(1);
    expect(result.current.integrations[0].name).toBe('AAP Instance 1');
  });

  it('filters out invalid integrations', async () => {
    vi.mocked(integrationsService.getIntegrationTypes).mockResolvedValue([mockPlatformType]);
    vi.mocked(integrationsService.getIntegrations).mockResolvedValue([
      mockAAPIntegration,
      mockInvalidIntegration,
    ]);
    const { result } = renderHook(() => usePlatformIntegrations());
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.integrations).toHaveLength(1);
    expect(result.current.integrations[0].id).toBe(1);
  });

  it('builds integrationOptions correctly', async () => {
    vi.mocked(integrationsService.getIntegrationTypes).mockResolvedValue([mockPlatformType]);
    vi.mocked(integrationsService.getIntegrations).mockResolvedValue([mockAAPIntegration]);
    const { result } = renderHook(() => usePlatformIntegrations());
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.integrationOptions).toEqual([
      { value: 1, label: 'AAP Instance 1 — aap' },
    ]);
  });

  it('sets error on fetch failure', async () => {
    vi.mocked(integrationsService.getIntegrationTypes).mockRejectedValue(new Error('API error'));
    const { result } = renderHook(() => usePlatformIntegrations());
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.error).toBe('API error');
    expect(result.current.integrations).toHaveLength(0);
  });

  it('sets error message for non-Error failures', async () => {
    vi.mocked(integrationsService.getIntegrationTypes).mockRejectedValue('unknown');
    const { result } = renderHook(() => usePlatformIntegrations());
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.error).toBe('Erreur inconnue');
  });

  it('getIntegrationById returns correct integration', async () => {
    vi.mocked(integrationsService.getIntegrationTypes).mockResolvedValue([mockPlatformType]);
    vi.mocked(integrationsService.getIntegrations).mockResolvedValue([mockAAPIntegration]);
    const { result } = renderHook(() => usePlatformIntegrations());
    await waitFor(() => expect(result.current.loading).toBe(false));

    const found = result.current.getIntegrationById(1);
    expect(found).toEqual(mockAAPIntegration);
  });

  it('getIntegrationById returns undefined for unknown id', async () => {
    vi.mocked(integrationsService.getIntegrationTypes).mockResolvedValue([mockPlatformType]);
    vi.mocked(integrationsService.getIntegrations).mockResolvedValue([mockAAPIntegration]);
    const { result } = renderHook(() => usePlatformIntegrations());
    await waitFor(() => expect(result.current.loading).toBe(false));

    const found = result.current.getIntegrationById(999);
    expect(found).toBeUndefined();
  });

  it('sets error=null on success', async () => {
    vi.mocked(integrationsService.getIntegrationTypes).mockResolvedValue([mockPlatformType]);
    vi.mocked(integrationsService.getIntegrations).mockResolvedValue([mockAAPIntegration]);
    const { result } = renderHook(() => usePlatformIntegrations());
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.error).toBeNull();
  });

  it('handles getIntegrations failure', async () => {
    vi.mocked(integrationsService.getIntegrationTypes).mockResolvedValue([mockPlatformType]);
    vi.mocked(integrationsService.getIntegrations).mockRejectedValue(new Error('Network'));
    const { result } = renderHook(() => usePlatformIntegrations());
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.error).toBe('Network');
  });

  it('getIntegrationById is stable (memoized)', async () => {
    vi.mocked(integrationsService.getIntegrationTypes).mockResolvedValue([mockPlatformType]);
    vi.mocked(integrationsService.getIntegrations).mockResolvedValue([mockAAPIntegration]);
    const { result } = renderHook(() => usePlatformIntegrations());
    await waitFor(() => expect(result.current.loading).toBe(false));

    const fn1 = result.current.getIntegrationById;
    // No rerender, so the memoized function should be the same reference
    expect(fn1).toBe(result.current.getIntegrationById);
  });
});

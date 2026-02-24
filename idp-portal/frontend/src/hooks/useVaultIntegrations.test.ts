/**
 * Tests for useVaultIntegrations hook (Story 39.7 — coverage).
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { useVaultIntegrations } from './useVaultIntegrations';
import * as integrationsService from '../services/integrations_service';
import type { IntegrationResponse } from '../types/api';

vi.mock('../services/integrations_service');

const mockVaultIntegration: IntegrationResponse = {
  id: 1,
  name: 'HashiCorp Vault',
  type: 'vault',
  base_url: 'https://vault.example.com',
  credential_ref: null,
  icon: null,
  auth_flow: null,
  status: 'valid',
  config: {},
  created_at: '2025-01-01T00:00:00Z',
  updated_at: '2025-01-01T00:00:00Z',
};

const mockOtherIntegration: IntegrationResponse = {
  id: 2,
  name: 'AAP Platform',
  type: 'aap',
  base_url: 'https://aap.example.com',
  credential_ref: null,
  icon: null,
  auth_flow: null,
  status: 'valid',
  config: {},
  created_at: '2025-01-01T00:00:00Z',
  updated_at: '2025-01-01T00:00:00Z',
};

const mockInvalidVault: IntegrationResponse = {
  ...mockVaultIntegration,
  id: 3,
  status: 'invalid',
};

describe('useVaultIntegrations', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('starts with loading=true', () => {
    vi.mocked(integrationsService.getIntegrations).mockResolvedValue([]);
    const { result } = renderHook(() => useVaultIntegrations());
    expect(result.current.loading).toBe(true);
  });

  it('returns only vault integrations after fetch', async () => {
    vi.mocked(integrationsService.getIntegrations).mockResolvedValue([
      mockVaultIntegration,
      mockOtherIntegration,
    ]);
    const { result } = renderHook(() => useVaultIntegrations());
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.vaultIntegrations).toHaveLength(1);
    expect(result.current.vaultIntegrations[0].name).toBe('HashiCorp Vault');
  });

  it('filters out invalid vault integrations', async () => {
    vi.mocked(integrationsService.getIntegrations).mockResolvedValue([
      mockVaultIntegration,
      mockInvalidVault,
    ]);
    const { result } = renderHook(() => useVaultIntegrations());
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.vaultIntegrations).toHaveLength(1);
    expect(result.current.vaultIntegrations[0].id).toBe(1);
  });

  it('sets error on fetch failure', async () => {
    vi.mocked(integrationsService.getIntegrations).mockRejectedValue(new Error('Network error'));
    const { result } = renderHook(() => useVaultIntegrations());
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.error).toBe('Network error');
    expect(result.current.vaultIntegrations).toHaveLength(0);
  });

  it('sets error message for non-Error failures', async () => {
    vi.mocked(integrationsService.getIntegrations).mockRejectedValue('unknown error');
    const { result } = renderHook(() => useVaultIntegrations());
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.error).toBe('Erreur inconnue');
  });

  it('sets error=null on success', async () => {
    vi.mocked(integrationsService.getIntegrations).mockResolvedValue([mockVaultIntegration]);
    const { result } = renderHook(() => useVaultIntegrations());
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.error).toBeNull();
  });

  it('returns empty array when no vault integrations exist', async () => {
    vi.mocked(integrationsService.getIntegrations).mockResolvedValue([mockOtherIntegration]);
    const { result } = renderHook(() => useVaultIntegrations());
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.vaultIntegrations).toHaveLength(0);
  });
});

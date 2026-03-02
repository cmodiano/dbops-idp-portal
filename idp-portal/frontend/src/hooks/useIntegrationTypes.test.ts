/**
 * Tests for useIntegrationTypes hook (Story 24.2 AC1).
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { useIntegrationTypes } from './useIntegrationTypes';
import type { IntegrationTypeCatalogue } from '../types/api';

vi.mock('../services/integrations_service', () => ({
  getIntegrationTypes: vi.fn(),
}));

import { getIntegrationTypes } from '../services/integrations_service';

const mockGetIntegrationTypes = vi.mocked(getIntegrationTypes);

const mockTypes: IntegrationTypeCatalogue[] = [
  {
    code: 'aap',
    name: 'Ansible Automation Platform',
    description: 'Exécution de jobs Ansible',
    version: '1.0',
    is_active: true,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
    actions: [
      {
        id: 1,
        action_code: 'start_job',
        action_label: 'Démarrer un job',
        description: 'Lance un job template AAP',
        required_params: { properties: { job_template_id: { type: 'integer', description: 'ID du job template' } } },
        optional_params: { properties: { extra_vars: { type: 'object', description: 'Variables extra' } } },
        response_format: {},
        is_active: true,
        created_at: '2026-01-01T00:00:00Z',
        updated_at: '2026-01-01T00:00:00Z',
      },
    ],
  },
  {
    code: 'servicenow',
    name: 'ServiceNow ITSM',
    description: 'Gestion des change requests',
    version: '1.1',
    is_active: true,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
    actions: [],
  },
];

describe('useIntegrationTypes', () => {
  beforeEach(() => {
    sessionStorage.clear();
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('fetches types from API on mount and returns them', async () => {
    mockGetIntegrationTypes.mockResolvedValue(mockTypes);

    const { result } = renderHook(() => useIntegrationTypes());

    expect(result.current.loading).toBe(true);

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.types).toEqual(mockTypes);
    expect(result.current.error).toBeNull();
    expect(result.current.isFallback).toBe(false);
    expect(mockGetIntegrationTypes).toHaveBeenCalledTimes(1);
  });

  it('returns fallback types and sets error on API failure', async () => {
    mockGetIntegrationTypes.mockRejectedValue(new Error('Network error'));

    const { result } = renderHook(() => useIntegrationTypes());

    // Wait for initial + 1 retry (1s delay)
    await waitFor(
      () => {
        expect(result.current.loading).toBe(false);
      },
      { timeout: 3000 }
    );

    expect(result.current.error).toBe('Network error');
    expect(result.current.isFallback).toBe(true);
    expect(result.current.types).toHaveLength(2);
    expect(result.current.types[0].code).toBe('aap');
    expect(result.current.types[1].code).toBe('servicenow');
    expect(mockGetIntegrationTypes).toHaveBeenCalledTimes(2); // Initial + 1 retry
  });

  it('uses sessionStorage cache and does not re-fetch', async () => {
    const cacheData = {
      data: mockTypes,
      timestamp: Date.now(),
    };
    sessionStorage.setItem('integration_types_cache', JSON.stringify(cacheData));

    const { result } = renderHook(() => useIntegrationTypes());

    // Should load from cache immediately (no loading state)
    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.types).toEqual(mockTypes);
    expect(mockGetIntegrationTypes).not.toHaveBeenCalled();
  });

  it('re-fetches when cache TTL has expired', async () => {
    const expiredCache = {
      data: mockTypes,
      timestamp: Date.now() - 3700000, // > 1 hour ago
    };
    sessionStorage.setItem('integration_types_cache', JSON.stringify(expiredCache));
    mockGetIntegrationTypes.mockResolvedValue(mockTypes);

    const { result } = renderHook(() => useIntegrationTypes());

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(mockGetIntegrationTypes).toHaveBeenCalledTimes(1);
    expect(result.current.types).toEqual(mockTypes);
  });

  it('handles corrupted cache gracefully', async () => {
    sessionStorage.setItem('integration_types_cache', 'invalid-json');
    mockGetIntegrationTypes.mockResolvedValue(mockTypes);

    const { result } = renderHook(() => useIntegrationTypes());

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(mockGetIntegrationTypes).toHaveBeenCalledTimes(1);
    expect(result.current.types).toEqual(mockTypes);
  });

  it('handles cache with invalid structure', async () => {
    sessionStorage.setItem('integration_types_cache', JSON.stringify({ foo: 'bar' }));
    mockGetIntegrationTypes.mockResolvedValue(mockTypes);

    const { result } = renderHook(() => useIntegrationTypes());

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(mockGetIntegrationTypes).toHaveBeenCalledTimes(1);
  });

  it('handles empty data array from API (does not cache)', async () => {
    mockGetIntegrationTypes.mockResolvedValue([]);
    const { result } = renderHook(() => useIntegrationTypes());
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.types).toEqual([]);
    expect(result.current.isFallback).toBe(false);
    // Empty array not stored in cache
    expect(sessionStorage.getItem('integration_types_cache')).toBeNull();
  });

  it('stores fetched types in sessionStorage cache', async () => {
    mockGetIntegrationTypes.mockResolvedValue(mockTypes);

    renderHook(() => useIntegrationTypes());

    await waitFor(() => {
      const cached = sessionStorage.getItem('integration_types_cache');
      expect(cached).not.toBeNull();
    });

    const parsed = JSON.parse(sessionStorage.getItem('integration_types_cache')!);
    expect(parsed.data).toEqual(mockTypes);
    expect(typeof parsed.timestamp).toBe('number');
  });
});

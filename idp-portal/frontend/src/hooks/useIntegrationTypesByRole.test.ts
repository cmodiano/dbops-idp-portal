/**
 * Tests for useIntegrationTypesByRole hook (Story 29.1).
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook } from '@testing-library/react';
import { useIntegrationTypesByRole } from './useIntegrationTypesByRole';
import type { IntegrationTypeCatalogue } from '../types/api';

const mockPlatform: IntegrationTypeCatalogue = {
  code: 'aap',
  name: 'Ansible Automation Platform',
  description: 'Exécution de jobs Ansible',
  version: '1.0',
  is_active: true,
  integration_role: 'platform',
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
  actions: [],
};

const mockService: IntegrationTypeCatalogue = {
  code: 'vault',
  name: 'HashiCorp Vault',
  description: 'Résolution secrets',
  version: '1.0',
  is_active: true,
  integration_role: 'service',
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
  actions: [],
};

const mockTypes = [mockPlatform, mockService];

vi.mock('./useIntegrationTypes', () => ({
  useIntegrationTypes: vi.fn(),
}));

import { useIntegrationTypes } from './useIntegrationTypes';

const mockUseIntegrationTypes = vi.mocked(useIntegrationTypes);

beforeEach(() => {
  mockUseIntegrationTypes.mockReturnValue({
    types: mockTypes,
    loading: false,
    error: null,
    isFallback: false,
  });
});

describe('useIntegrationTypesByRole', () => {
  it('returns all types when no role filter is provided', () => {
    const { result } = renderHook(() => useIntegrationTypesByRole());
    expect(result.current.types).toHaveLength(2);
    expect(result.current.types).toEqual(mockTypes);
  });

  it('filters by platform role', () => {
    const { result } = renderHook(() => useIntegrationTypesByRole('platform'));
    expect(result.current.types).toHaveLength(1);
    expect(result.current.types[0].code).toBe('aap');
  });

  it('filters by service role', () => {
    const { result } = renderHook(() => useIntegrationTypesByRole('service'));
    expect(result.current.types).toHaveLength(1);
    expect(result.current.types[0].code).toBe('vault');
  });

  it('returns empty array when no matching role', () => {
    mockUseIntegrationTypes.mockReturnValue({
      types: [mockPlatform],
      loading: false,
      error: null,
      isFallback: false,
    });
    const { result } = renderHook(() => useIntegrationTypesByRole('service'));
    expect(result.current.types).toHaveLength(0);
  });

  it('passes through loading state', () => {
    mockUseIntegrationTypes.mockReturnValue({
      types: [],
      loading: true,
      error: null,
      isFallback: false,
    });
    const { result } = renderHook(() => useIntegrationTypesByRole('platform'));
    expect(result.current.loading).toBe(true);
  });

  it('passes through error state', () => {
    mockUseIntegrationTypes.mockReturnValue({
      types: [],
      loading: false,
      error: 'Network error',
      isFallback: true,
    });
    const { result } = renderHook(() => useIntegrationTypesByRole('platform'));
    expect(result.current.error).toBe('Network error');
    expect(result.current.isFallback).toBe(true);
  });
});

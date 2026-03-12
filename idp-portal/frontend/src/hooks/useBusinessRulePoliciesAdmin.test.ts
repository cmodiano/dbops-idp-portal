/**
 * Tests pour useBusinessRulePoliciesAdmin et useBusinessRulePoliciesActive (Story 71.1, AC3/AC4).
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, waitFor, act } from '@testing-library/react';
import { useBusinessRulePoliciesAdmin, useBusinessRulePoliciesActive } from './useBusinessRulePoliciesAdmin';
import * as service from '../services/business_rules_service';

vi.mock('../services/business_rules_service');
vi.mock('../services/logger', () => ({ default: { error: vi.fn(), warn: vi.fn(), debug: vi.fn() } }));

const mockPolicies = [
  { id: 1, name: 'Policy 1', description: null, step_type: 'aap', is_active: true, updated_at: '2025-01-01' },
  { id: 2, name: 'Policy 2', description: 'desc', step_type: 'terraform_cloud', is_active: false, updated_at: '2025-01-02' },
];

describe('useBusinessRulePoliciesAdmin', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(service.getBusinessRulePolicies).mockResolvedValue({ data: mockPolicies } as never);
  });

  it('charge les policies au montage', async () => {
    const { result } = renderHook(() => useBusinessRulePoliciesAdmin());

    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.policies).toHaveLength(2);
    expect(service.getBusinessRulePolicies).toHaveBeenCalled();
  });

  it('getOne appelle getBusinessRulePolicy', async () => {
    const mockDetail = { id: 1, name: 'Policy 1', rules: [] };
    vi.mocked(service.getBusinessRulePolicy).mockResolvedValue(mockDetail as never);

    const { result } = renderHook(() => useBusinessRulePoliciesAdmin());
    await waitFor(() => expect(result.current.loading).toBe(false));

    const detail = await result.current.getOne(1);
    expect(detail).toEqual(mockDetail);
    expect(service.getBusinessRulePolicy).toHaveBeenCalledWith(1);
  });

  it('create appelle createBusinessRulePolicy et refresh', async () => {
    const mockCreated = { id: 3, name: 'New' };
    vi.mocked(service.createBusinessRulePolicy).mockResolvedValue(mockCreated as never);

    const { result } = renderHook(() => useBusinessRulePoliciesAdmin());
    await waitFor(() => expect(result.current.loading).toBe(false));

    await act(async () => {
      await result.current.create({ name: 'New' } as never);
    });

    expect(service.createBusinessRulePolicy).toHaveBeenCalledWith({ name: 'New' });
    // Should have refetched
    expect(service.getBusinessRulePolicies).toHaveBeenCalledTimes(2);
  });

  it('remove appelle deleteBusinessRulePolicy et refresh', async () => {
    vi.mocked(service.deleteBusinessRulePolicy).mockResolvedValue(undefined);

    const { result } = renderHook(() => useBusinessRulePoliciesAdmin());
    await waitFor(() => expect(result.current.loading).toBe(false));

    await act(async () => {
      await result.current.remove(1);
    });

    expect(service.deleteBusinessRulePolicy).toHaveBeenCalledWith(1);
    expect(service.getBusinessRulePolicies).toHaveBeenCalledTimes(2);
  });
});

describe('useBusinessRulePoliciesActive', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(service.getBusinessRulePolicies).mockResolvedValue({ data: [mockPolicies[0]] } as never);
  });

  it('charge uniquement les policies actives', async () => {
    const { result } = renderHook(() => useBusinessRulePoliciesActive());

    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.policies).toHaveLength(1);
    expect(service.getBusinessRulePolicies).toHaveBeenCalledWith({ is_active: true });
    expect(result.current.error).toBeNull();
  });

  it('gère les erreurs', async () => {
    vi.mocked(service.getBusinessRulePolicies).mockRejectedValue(new Error('Network'));

    const { result } = renderHook(() => useBusinessRulePoliciesActive());

    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.error).toBe('Network');
    expect(result.current.policies).toEqual([]);
  });
});

/**
 * Tests unitaires pour useBusinessRulePolicies (Story 54.15, AC8).
 */

import { renderHook, waitFor } from '@testing-library/react';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import { useBusinessRulePolicies } from './useBusinessRulePolicies';
import { getBusinessRulePolicies } from '../services/business_rules_service';

vi.mock('../services/business_rules_service');
vi.mock('../services/logger', () => ({
  default: { error: vi.fn(), warn: vi.fn(), info: vi.fn() },
}));

const mockPolicies = [
  { id: 1, name: 'Policy AAP', step_type: 'aap', description: 'Règle AAP', is_active: true, created_at: '2024-01-01T00:00:00Z', updated_at: '2024-01-01T00:00:00Z' },
];

describe('useBusinessRulePolicies', () => {
  beforeEach(() => { vi.clearAllMocks(); });

  it('charge les policies quand stepType est fourni', async () => {
    vi.mocked(getBusinessRulePolicies).mockResolvedValue({ data: mockPolicies, pagination: null });

    const { result } = renderHook(() => useBusinessRulePolicies('aap'));
    expect(result.current.loading).toBe(true);

    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.policies).toEqual(mockPolicies);
    expect(result.current.error).toBeNull();
    expect(getBusinessRulePolicies).toHaveBeenCalledWith({ is_active: true, step_type: 'aap' });
  });

  it('retourne liste vide sans appel API quand stepType est vide', () => {
    const { result } = renderHook(() => useBusinessRulePolicies(''));
    expect(result.current.loading).toBe(false);
    expect(result.current.policies).toEqual([]);
    expect(getBusinessRulePolicies).not.toHaveBeenCalled();
  });

  it('retourne liste vide sans appel API quand stepType est null', () => {
    const { result } = renderHook(() => useBusinessRulePolicies(null));
    expect(result.current.loading).toBe(false);
    expect(result.current.policies).toEqual([]);
    expect(getBusinessRulePolicies).not.toHaveBeenCalled();
  });

  it('gère les erreurs de chargement', async () => {
    vi.mocked(getBusinessRulePolicies).mockRejectedValue(new Error('réseau'));

    const { result } = renderHook(() => useBusinessRulePolicies('aap'));
    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.error).toBe('réseau');
    expect(result.current.policies).toEqual([]);
  });

  it('recharge quand stepType change', async () => {
    vi.mocked(getBusinessRulePolicies).mockResolvedValue({ data: mockPolicies, pagination: null });

    const { result, rerender } = renderHook(
      ({ stepType }: { stepType: string }) => useBusinessRulePolicies(stepType),
      { initialProps: { stepType: 'aap' } }
    );
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(getBusinessRulePolicies).toHaveBeenCalledTimes(1);

    rerender({ stepType: 'terraform_cloud' });
    await waitFor(() => expect(getBusinessRulePolicies).toHaveBeenCalledTimes(2));
    expect(getBusinessRulePolicies).toHaveBeenLastCalledWith({ is_active: true, step_type: 'terraform_cloud' });
  });

  it('cancelled flag — composant démonté avant réponse', async () => {
    vi.mocked(getBusinessRulePolicies).mockImplementation(
      () => new Promise((resolve) => setTimeout(() => resolve({ data: [], pagination: null }), 100))
    );
    const { result, unmount } = renderHook(() => useBusinessRulePolicies('aap'));
    unmount();
    await new Promise((r) => setTimeout(r, 150));
    expect(result.current.policies).toEqual([]);
  });
});

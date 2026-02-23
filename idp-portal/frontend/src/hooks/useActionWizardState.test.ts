/**
 * Tests pour useActionWizardState (Story 35.3, Task 4.3).
 * Vérifie que le hook encapsule correctement les appels de service admin_service.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { useActionWizardState } from './useActionWizardState';

vi.mock('../services/admin_service', () => ({
  getTags: vi.fn().mockResolvedValue([
    { name: 'oracle' },
    { name: 'provisioning' },
  ]),
  updateActionTags: vi.fn().mockResolvedValue({}),
  updateActionSteps: vi.fn().mockResolvedValue({}),
  updateWorkflowSteps: vi.fn().mockResolvedValue({}),
  updateBusinessRulePolicies: vi.fn().mockResolvedValue({}),
  patchAction: vi.fn().mockResolvedValue({ id: 1 }),
}));

import {
  getTags,
  updateActionTags,
  updateActionSteps,
  updateWorkflowSteps,
  updateBusinessRulePolicies,
  patchAction,
} from '../services/admin_service';

describe('useActionWizardState', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('charge les tagsOptions au montage quand open=true', async () => {
    const { result } = renderHook(() => useActionWizardState({ open: true }));

    await waitFor(() => {
      expect(result.current.tagsOptions).toHaveLength(2);
    });

    expect(result.current.tagsOptions).toEqual([
      { value: 'oracle', label: 'oracle' },
      { value: 'provisioning', label: 'provisioning' },
    ]);
    expect(getTags).toHaveBeenCalledTimes(1);
  });

  it('ne charge pas les tags quand open=false', () => {
    renderHook(() => useActionWizardState({ open: false }));
    expect(getTags).not.toHaveBeenCalled();
  });

  it('handleUpdateActionTags appelle updateActionTags avec les bons arguments', async () => {
    const { result } = renderHook(() => useActionWizardState({ open: true }));

    await result.current.handleUpdateActionTags(42, ['oracle', 'provisioning']);

    expect(updateActionTags).toHaveBeenCalledWith(42, { tag_names: ['oracle', 'provisioning'] });
  });

  it('handleUpdateActionSteps appelle updateActionSteps avec le payload', async () => {
    const { result } = renderHook(() => useActionWizardState({ open: true }));
    const payload = { steps: [], change_type_config: null };

    await result.current.handleUpdateActionSteps(1, payload);

    expect(updateActionSteps).toHaveBeenCalledWith(1, payload);
  });

  it('handleUpdateWorkflowSteps appelle updateWorkflowSteps', async () => {
    const { result } = renderHook(() => useActionWizardState({ open: true }));
    const payload = { steps: [] };

    await result.current.handleUpdateWorkflowSteps(5, payload);

    expect(updateWorkflowSteps).toHaveBeenCalledWith(5, payload);
  });

  it('handleUpdateBusinessRulePolicies appelle updateBusinessRulePolicies', async () => {
    const { result } = renderHook(() => useActionWizardState({ open: true }));

    await result.current.handleUpdateBusinessRulePolicies(10, null);

    expect(updateBusinessRulePolicies).toHaveBeenCalledWith(10, null);
  });

  it('handlePatchAction appelle patchAction avec le payload partiel', async () => {
    const { result } = renderHook(() => useActionWizardState({ open: true }));

    await result.current.handlePatchAction(7, { business_rule_policy_id: 3 });

    expect(patchAction).toHaveBeenCalledWith(7, { business_rule_policy_id: 3 });
  });

  it('retourne des tagsOptions vides si getTags échoue', async () => {
    vi.mocked(getTags).mockRejectedValueOnce(new Error('Network error'));
    const { result } = renderHook(() => useActionWizardState({ open: true }));

    await waitFor(() => {
      // Après l'échec, tagsOptions reste []
      expect(result.current.tagsOptions).toEqual([]);
    });
  });
});

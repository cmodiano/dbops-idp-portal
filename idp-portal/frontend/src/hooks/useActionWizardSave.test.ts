/**
 * Tests unitaires pour useActionWizardSave (Story 88-6, SMELL-FE-01, AC #4-#5).
 */
import { describe, it, expect, vi } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useActionWizardSave } from './useActionWizardSave';
import type { UseActionWizardSaveParams } from './useActionWizardSave';

function makeParams(overrides: Partial<UseActionWizardSaveParams> = {}): UseActionWizardSaveParams {
  const mockForm = {
    getFieldValue: vi.fn((field: string) => {
      if (field === 'item_type') return 'action';
      return undefined;
    }),
    getFieldsValue: vi.fn(() => ({
      item_type: 'action',
      name: 'Test Action',
      engine: 'ansible',
      integration_id: 1,
    })),
    validateFields: vi.fn().mockResolvedValue({
      name: 'Test Action',
      description: 'Desc',
      engine: 'ansible',
      integration_id: 1,
      item_type: 'action',
    }),
    setFields: vi.fn(),
  };

  return {
    form: mockForm as unknown as UseActionWizardSaveParams['form'],
    _step1ValuesRef: { current: null },
    setSubmitError: vi.fn(),
    setSaving: vi.fn(),
    validateForSave: vi.fn(() => null),
    parameterList: [],
    impactRulesList: [],
    platformCap: null,
    actionConfig: {},
    defaultImpactLevel: null,
    outputSchemaId: null,
    selectedTags: [],
    initialTags: [],
    workflowSteps: [],
    editAction: null,
    onSubmit: vi.fn().mockResolvedValue({ id: 42, name: 'Test Action' }),
    onSuccess: vi.fn(),
    handleUpdateActionTags: vi.fn().mockResolvedValue(undefined),
    handleUpdateWorkflowSteps: vi.fn().mockResolvedValue(undefined),
    handleUpdateActionSteps: vi.fn().mockResolvedValue(undefined),
    getIntegrationById: vi.fn(() => undefined),
    notification: {
      warning: vi.fn(),
      info: vi.fn(),
    },
    ...overrides,
  };
}

describe('useActionWizardSave', () => {
  it('retourne handleSave comme fonction', () => {
    const { result } = renderHook(() => useActionWizardSave(makeParams()));
    expect(typeof result.current.handleSave).toBe('function');
  });

  it('cas succès — onSubmit + handleUpdateActionSteps + onSuccess appelés', async () => {
    const params = makeParams();
    const { result } = renderHook(() => useActionWizardSave(params));

    await act(async () => {
      await result.current.handleSave();
    });

    expect(params.onSubmit).toHaveBeenCalledOnce();
    expect(params.handleUpdateActionSteps).toHaveBeenCalledOnce();
    expect(params.onSuccess).toHaveBeenCalledWith(expect.objectContaining({ id: 42 }));
    expect(params.setSubmitError).toHaveBeenCalledWith(null); // reset at start
    expect(params.setSaving).toHaveBeenCalledWith(true);
    expect(params.setSaving).toHaveBeenCalledWith(false); // finally
  });

  it('cas erreur validation — setSubmitError appelé, onSubmit non appelé', async () => {
    const params = makeParams({
      validateForSave: vi.fn(() => 'Erreur: template AAP requis'),
    });
    const { result } = renderHook(() => useActionWizardSave(params));

    await act(async () => {
      await result.current.handleSave();
    });

    expect(params.setSubmitError).toHaveBeenCalledWith('Erreur: template AAP requis');
    expect(params.onSubmit).not.toHaveBeenCalled();
  });

  it('cas erreur tag — notification.warning + onSuccess toujours appelés', async () => {
    const params = makeParams({
      selectedTags: ['new-tag'],
      initialTags: [],
      handleUpdateActionTags: vi.fn().mockRejectedValue(new Error('Tag API error')),
    });
    const { result } = renderHook(() => useActionWizardSave(params));

    await act(async () => {
      await result.current.handleSave();
    });

    expect(params.notification.warning).toHaveBeenCalledWith(
      expect.objectContaining({ message: 'Tags non mis à jour' })
    );
    expect(params.onSuccess).toHaveBeenCalled();
  });

  it('cas workflow save — handleUpdateWorkflowSteps appelé, handleUpdateActionSteps non appelé', async () => {
    const mockForm = {
      getFieldValue: vi.fn((field: string) => {
        if (field === 'item_type') return 'workflow';
        return undefined;
      }),
      getFieldsValue: vi.fn(() => ({
        item_type: 'workflow',
        name: 'Test Workflow',
      })),
      validateFields: vi.fn().mockResolvedValue({
        name: 'Test Workflow',
        item_type: 'workflow',
      }),
      setFields: vi.fn(),
    };

    const params = makeParams({
      form: mockForm as unknown as UseActionWizardSaveParams['form'],
      workflowSteps: [
        {
          step_id: 'step-1',
          step_type: 'platform',
          referenced_action_id: 1,
          name: 'Étape 1',
          order: 1,
          on_success_step_ids: [],
          on_error_step_ids: [],
        },
      ],
    });

    const { result } = renderHook(() => useActionWizardSave(params));

    await act(async () => {
      await result.current.handleSave();
    });

    expect(params.handleUpdateWorkflowSteps).toHaveBeenCalledOnce();
    expect(params.handleUpdateActionSteps).not.toHaveBeenCalled();
    expect(params.onSuccess).toHaveBeenCalled();
  });
});

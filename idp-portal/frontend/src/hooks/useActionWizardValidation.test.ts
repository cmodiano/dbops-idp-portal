import { describe, it, expect, vi } from 'vitest';
import { renderHook } from '@testing-library/react';
import { useActionWizardValidation } from './useActionWizardValidation';
import type { ActionWizardValidationParams } from './useActionWizardValidation';

const mockValidateWorkflowSteps = vi.fn(() => true);

const baseParams: ActionWizardValidationParams = {
  isWorkflowSave: false,
  parameterList: [],
  impactRulesList: [],
  platformCap: null,
  actionConfig: {},
  integrationId: undefined,
  getIntegrationById: vi.fn(() => undefined),
};

describe('useActionWizardValidation', () => {
  it('retourne validateForSave comme fonction', () => {
    const { result } = renderHook(() =>
      useActionWizardValidation({ validateWorkflowSteps: mockValidateWorkflowSteps })
    );
    expect(typeof result.current.validateForSave).toBe('function');
  });

  it('retourne null pour des paramètres valides (action)', () => {
    const { result } = renderHook(() =>
      useActionWizardValidation({ validateWorkflowSteps: mockValidateWorkflowSteps })
    );
    expect(result.current.validateForSave(baseParams)).toBeNull();
  });

  it('délègue à validateWorkflowSteps pour un workflow', () => {
    const validateSteps = vi.fn(() => true);
    const { result } = renderHook(() =>
      useActionWizardValidation({ validateWorkflowSteps: validateSteps })
    );
    const params = { ...baseParams, isWorkflowSave: true };
    const error = result.current.validateForSave(params);
    expect(validateSteps).toHaveBeenCalled();
    expect(error).toBeNull();
  });

  it('retourne signal interne quand validateWorkflowSteps retourne false', () => {
    const validateSteps = vi.fn(() => false);
    const { result } = renderHook(() =>
      useActionWizardValidation({ validateWorkflowSteps: validateSteps })
    );
    const params = { ...baseParams, isWorkflowSave: true };
    const error = result.current.validateForSave(params);
    expect(error).toBe('__workflow_steps_invalid__');
  });

  it('retourne erreur si paramètre avec nom vide', () => {
    const { result } = renderHook(() =>
      useActionWizardValidation({ validateWorkflowSteps: mockValidateWorkflowSteps })
    );
    const params = {
      ...baseParams,
      parameterList: [{ id: '1', name: '', type: 'string' as const, required: false }],
    };
    const error = result.current.validateForSave(params);
    expect(error).toMatch(/paramètre 1 doit avoir un nom/);
  });

  it('retourne erreur si règles d\'impact avec envs dupliqués', () => {
    const { result } = renderHook(() =>
      useActionWizardValidation({ validateWorkflowSteps: mockValidateWorkflowSteps })
    );
    const params = {
      ...baseParams,
      impactRulesList: [
        { environment: 'PROD', level: 'high' as const, criteria: null },
        { environment: 'PROD', level: 'low' as const, criteria: null },
      ],
    };
    const error = result.current.validateForSave(params);
    expect(error).toMatch(/Deux règles d'impact utilisent l'environnement "PROD"/);
  });

  it('retourne erreur si AAP sans template sélectionné', () => {
    const getIntegrationById = vi.fn(() => ({ id: 1, type: 'aap', name: 'AAP-PROD' }));
    const { result } = renderHook(() =>
      useActionWizardValidation({ validateWorkflowSteps: mockValidateWorkflowSteps })
    );
    const params = {
      ...baseParams,
      integrationId: 1,
      getIntegrationById,
      actionConfig: {},
    };
    const error = result.current.validateForSave(params);
    expect(error).toMatch(/ID du template.*requis/);
  });
});

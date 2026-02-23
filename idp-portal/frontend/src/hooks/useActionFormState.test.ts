import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { Form } from 'antd';
import { useActionFormState } from './useActionFormState';
import type { ActionDetail } from '../types/api';

vi.mock('../services/admin_service', () => ({
  getTags: vi.fn().mockResolvedValue([{ name: 'oracle' }, { name: 'postgres' }]),
}));

vi.mock('../utils/parametersSchema', () => ({
  parameterListToSchema: vi.fn(() => null),
  schemaToParameterList: vi.fn(() => []),
}));

vi.mock('../utils/impactRulesSchema', () => ({
  impactRulesToList: vi.fn(() => []),
}));

vi.mock('../utils/integrationHelpers', () => ({
  integrationTypeToPlatformCode: vi.fn((type: string) => type?.toUpperCase() ?? ''),
}));

const mockGetIntegrationById = vi.fn();

function renderStateHook(open: boolean, editAction?: ActionDetail | null) {
  return renderHook(() => {
    const [form] = Form.useForm();
    return useActionFormState({ open, editAction: editAction ?? null, form, getIntegrationById: mockGetIntegrationById });
  });
}

describe('useActionFormState', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('initialise avec des états vides quand open=false', () => {
    const { result } = renderStateHook(false);

    expect(result.current.executionSteps).toEqual([]);
    expect(result.current.parameterList).toEqual([]);
    expect(result.current.impactRulesList).toEqual([]);
    expect(result.current.selectedTags).toEqual([]);
    expect(result.current.stepsError).toBeNull();
    expect(result.current.saving).toBe(false);
  });

  it('expose les setters pour toutes les valeurs d\'état', () => {
    const { result } = renderStateHook(true);

    expect(typeof result.current.setStepsError).toBe('function');
    expect(typeof result.current.setSaving).toBe('function');
    expect(typeof result.current.setExecutionSteps).toBe('function');
    expect(typeof result.current.setChangeTypeConfig).toBe('function');
    expect(typeof result.current.setParameterList).toBe('function');
    expect(typeof result.current.setImpactRulesList).toEqual('function');
    expect(typeof result.current.setDefaultImpactLevel).toBe('function');
    expect(typeof result.current.setSelectedTags).toBe('function');
    expect(typeof result.current.setGateConfig).toBe('function');
    expect(typeof result.current.setNotificationConfig).toBe('function');
  });

  it('expose nameInputRef', () => {
    const { result } = renderStateHook(true);
    expect(result.current.nameInputRef).toBeDefined();
    expect(result.current.nameInputRef.current).toBe(null); // pas attaché à un DOM
  });

  it('expose previewData avec des valeurs vides par défaut', () => {
    const { result } = renderStateHook(true);
    expect(result.current.previewData).toBeDefined();
    expect(result.current.previewData.name).toBe('');
    expect(result.current.previewData.tags).toEqual([]);
  });

  it('reset les états quand open passe à false', async () => {
    const { result, rerender } = renderHook(
      ({ open }: { open: boolean }) => {
        const [form] = Form.useForm();
        return useActionFormState({ open, editAction: null, form, getIntegrationById: mockGetIntegrationById });
      },
      { initialProps: { open: true } }
    );

    // Modifier un état
    act(() => {
      result.current.setStepsError('some error');
      result.current.setSaving(true);
    });
    expect(result.current.stepsError).toBe('some error');

    // Fermer le modal → reset
    rerender({ open: false });
    expect(result.current.stepsError).toBeNull();
    expect(result.current.saving).toBe(false);
  });

  it('initialise depuis editAction en mode edit', async () => {
    const { impactRulesToList } = vi.mocked(await import('../utils/impactRulesSchema'));
    const mockImpactRules = [{ environment: 'PROD', level: 'high' as const }];
    impactRulesToList.mockReturnValue(mockImpactRules);

    const editAction: ActionDetail = {
      id: 1,
      name: 'Test',
      description: 'Desc',
      item_type: 'action',
      engine: 'Oracle',
      platform: 'AAP',
      integration_id: 1,
      parameters_schema: null,
      impact_rules: { PROD: { level: 'high' } },
      default_impact_level: 'high',
      status: 'draft',
      created_by: 1,
      created_at: '2026-01-01T00:00:00Z',
      updated_at: null,
      execution_steps: null,
      workflow_steps: null,
      change_type_config: null,
      tags: ['oracle', 'prod'],
    };

    const { result } = renderStateHook(true, editAction);
    expect(result.current.selectedTags).toEqual(['oracle', 'prod']);
    expect(result.current.defaultImpactLevel).toBe('high');
  });
});

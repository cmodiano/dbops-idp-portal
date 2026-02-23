import { describe, it, expect } from 'vitest';
import { renderHook } from '@testing-library/react';
import {
  useActionFormValidation,
  validateParameterList,
  validateImpactRulesList,
  validateChangeTypeConfig,
} from './useActionFormValidation';
import type { ActionFormValidationParams } from './useActionFormValidation';

const baseParams: ActionFormValidationParams = {
  isEditMode: false,
  executionSteps: [],
  parameterList: [],
  impactRulesList: [],
  changeTypeConfig: {},
  snIntegrationOptions: [],
  gateConfig: null,
};

// ─── validateParameterList ────────────────────────────────────────────────────

describe('validateParameterList', () => {
  it('retourne null pour une liste vide', () => {
    expect(validateParameterList([])).toBeNull();
  });

  it('retourne erreur si nom de paramètre vide', () => {
    const error = validateParameterList([{ id: '1', name: '', type: 'string' as const, required: false }]);
    expect(error).toMatch(/paramètre 1 doit avoir un nom/);
  });

  it('retourne erreur si deux paramètres ont le même nom', () => {
    const params = [
      { id: '1', name: 'param1', type: 'string' as const, required: false },
      { id: '2', name: 'param1', type: 'string' as const, required: false },
    ];
    const error = validateParameterList(params);
    expect(error).toMatch(/Deux paramètres ont le même nom "param1"/);
  });

  it('retourne null pour des paramètres valides', () => {
    const params = [
      { id: '1', name: 'param1', type: 'string' as const, required: false },
      { id: '2', name: 'param2', type: 'number' as const, required: true },
    ];
    expect(validateParameterList(params)).toBeNull();
  });
});

// ─── validateImpactRulesList ──────────────────────────────────────────────────

describe('validateImpactRulesList', () => {
  it('retourne null pour une liste vide', () => {
    expect(validateImpactRulesList([])).toBeNull();
  });

  it('retourne erreur si environnement manquant', () => {
    const rules = [{ environment: '', level: 'low' as const, criteria: null }];
    const error = validateImpactRulesList(rules);
    expect(error).toMatch(/règle d'impact 1 doit avoir un environnement/);
  });

  it('retourne erreur si environnements dupliqués', () => {
    const rules = [
      { environment: 'PROD', level: 'high' as const, criteria: null },
      { environment: 'PROD', level: 'low' as const, criteria: null },
    ];
    const error = validateImpactRulesList(rules);
    expect(error).toMatch(/Deux règles d'impact utilisent l'environnement "PROD"/);
  });

  it('retourne erreur si niveau manquant', () => {
    const rules = [{ environment: 'PROD', level: undefined as unknown as 'low', criteria: null }];
    const error = validateImpactRulesList(rules);
    expect(error).toMatch(/règle d'impact 1 doit avoir un niveau/);
  });

  it('retourne null pour des règles valides', () => {
    const rules = [
      { environment: 'DEV', level: 'low' as const, criteria: null },
      { environment: 'PROD', level: 'high' as const, criteria: null },
    ];
    expect(validateImpactRulesList(rules)).toBeNull();
  });
});

// ─── validateChangeTypeConfig ─────────────────────────────────────────────────

describe('validateChangeTypeConfig', () => {
  it('retourne null si aucune entrée requise', () => {
    const config = { PROD: { required: false } };
    expect(validateChangeTypeConfig(config, [], null)).toBeNull();
  });

  it('retourne erreur si required=true sans intégration SN sélectionnée', () => {
    const config = { PROD: { required: true, change_model_code: 'CHG001' } };
    const snOptions = [{ value: 1, label: 'SN-PROD' }];
    const error = validateChangeTypeConfig(config, snOptions, null);
    expect(error).toMatch(/intégration ServiceNow doit être sélectionnée/);
  });

  it('retourne erreur si template_id vide quand required=true', () => {
    const config = { PROD: { required: true, template_id: '' } };
    const error = validateChangeTypeConfig(config, [], null);
    expect(error).toMatch(/obligatoire pour PROD/);
  });

  it('retourne erreur si code non alphanumérique', () => {
    const config = { PROD: { required: true, template_id: 'CHG @001!' } };
    const error = validateChangeTypeConfig(config, [], null);
    expect(error).toMatch(/alphanumérique/);
  });

  it('retourne erreur si code > 50 caractères', () => {
    const config = { PROD: { required: true, template_id: 'A'.repeat(51) } };
    const error = validateChangeTypeConfig(config, [], null);
    expect(error).toMatch(/50 caractères/);
  });

  it('retourne null pour une config valide avec gateConfig SN', () => {
    const config = { PROD: { required: true, template_id: 'CHG_TPL_001' } };
    const snOptions = [{ value: 1, label: 'SN-PROD' }];
    const gateConfig = { servicenow_change: { integration_id: 1 } };
    expect(validateChangeTypeConfig(config, snOptions, gateConfig)).toBeNull();
  });
});

// ─── useActionFormValidation ──────────────────────────────────────────────────

describe('useActionFormValidation', () => {
  it('retourne validateForm comme fonction', () => {
    const { result } = renderHook(() => useActionFormValidation());
    expect(typeof result.current.validateForm).toBe('function');
  });

  it('retourne null pour des paramètres valides', () => {
    const { result } = renderHook(() => useActionFormValidation());
    expect(result.current.validateForm(baseParams)).toBeNull();
  });

  it('retourne erreur en mode edit sans étape', () => {
    const { result } = renderHook(() => useActionFormValidation());
    const params = { ...baseParams, isEditMode: true, executionSteps: [] };
    const error = result.current.validateForm(params);
    expect(error).toMatch(/Au moins une étape est requise/);
  });

  it('retourne null en mode création (isEditMode=false) sans étape — comportement intentionnel', () => {
    const { result } = renderHook(() => useActionFormValidation());
    const params = { ...baseParams, isEditMode: false, executionSteps: [] };
    expect(result.current.validateForm(params)).toBeNull();
  });

  it('retourne erreur si étape sans nom', () => {
    const { result } = renderHook(() => useActionFormValidation());
    const params = {
      ...baseParams,
      executionSteps: [{ order: 1, name: '', type: 'execution' as const, connector_type: 'none' as const, conditional_environments: null }],
    };
    const error = result.current.validateForm(params);
    expect(error).toMatch(/L'étape 1 doit avoir un nom/);
  });

  it('retourne erreur si paramètre avec nom vide', () => {
    const { result } = renderHook(() => useActionFormValidation());
    const params = {
      ...baseParams,
      parameterList: [{ id: '1', name: '', type: 'string' as const, required: false }],
    };
    const error = result.current.validateForm(params);
    expect(error).toMatch(/paramètre 1 doit avoir un nom/);
  });

  it('retourne erreur si règles d\'impact avec envs dupliqués', () => {
    const { result } = renderHook(() => useActionFormValidation());
    const params = {
      ...baseParams,
      impactRulesList: [
        { environment: 'DEV', level: 'low' as const, criteria: null },
        { environment: 'DEV', level: 'high' as const, criteria: null },
      ],
    };
    const error = result.current.validateForm(params);
    expect(error).toMatch(/Deux règles d'impact utilisent l'environnement "DEV"/);
  });

  it('retourne erreur si changeTypeConfig sans intégration SN', () => {
    const { result } = renderHook(() => useActionFormValidation());
    const params = {
      ...baseParams,
      changeTypeConfig: { PROD: { required: true, template_id: 'CHG001' } },
      snIntegrationOptions: [{ value: 1, label: 'SN-PROD' }],
      gateConfig: null,
    };
    const error = result.current.validateForm(params);
    expect(error).toMatch(/intégration ServiceNow/);
  });
});

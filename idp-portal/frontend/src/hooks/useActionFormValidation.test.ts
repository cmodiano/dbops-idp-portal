import { describe, it, expect } from 'vitest';
import { renderHook } from '@testing-library/react';
import {
  useActionFormValidation,
  validateParameterList,
  validateImpactRulesList,
} from './useActionFormValidation';
import type { ActionFormValidationParams } from './useActionFormValidation';

const baseParams: ActionFormValidationParams = {
  isEditMode: false,
  executionSteps: [],
  parameterList: [],
  impactRulesList: [],
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

});

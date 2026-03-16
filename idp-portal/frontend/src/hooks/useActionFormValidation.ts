/**
 * useActionFormValidation — Logique de validation extraite de ActionForm::handleFinish (Story 33.5, Task 3).
 * Expose aussi les helpers partagés validateParameterList et validateImpactRulesList,
 * réutilisables par useActionWizardValidation (AC6 — factorisation).
 */
import type {
  ExecutionStep,
  ImpactRuleDefinition,
  ParameterDefinition,
} from '../types/api';

// ─── Helpers partagés ────────────────────────────────────────────────────────

/** Valide une liste de paramètres. Retourne un message d'erreur ou null. */
export function validateParameterList(parameterList: ParameterDefinition[]): string | null {
  if (parameterList.length === 0) return null;
  const names = parameterList.map((p) => (p.name ?? '').trim());
  const emptyIndex = names.findIndex((n) => !n);
  if (emptyIndex >= 0) {
    return `Le paramètre ${emptyIndex + 1} doit avoir un nom.`;
  }
  const seen = new Set<string>();
  for (let i = 0; i < names.length; i++) {
    if (seen.has(names[i])) {
      return `Deux paramètres ont le même nom "${names[i]}". Chaque nom doit être unique.`;
    }
    seen.add(names[i]);
  }
  return null;
}

/** Valide une liste de règles d'impact. Retourne un message d'erreur ou null. */
export function validateImpactRulesList(impactRulesList: ImpactRuleDefinition[]): string | null {
  if (impactRulesList.length === 0) return null;
  const envs = impactRulesList.map((r) => (r.environment ?? '').trim());
  const emptyEnvIndex = envs.findIndex((e) => !e);
  if (emptyEnvIndex >= 0) {
    return `La règle d'impact ${emptyEnvIndex + 1} doit avoir un environnement.`;
  }
  const seenEnvs = new Set<string>();
  for (let i = 0; i < envs.length; i++) {
    if (seenEnvs.has(envs[i])) {
      return `Deux règles d'impact utilisent l'environnement "${envs[i]}". Chaque environnement doit être unique.`;
    }
    seenEnvs.add(envs[i]);
  }
  const missingLevelIndex = impactRulesList.findIndex((r) => !r.level);
  if (missingLevelIndex >= 0) {
    return `La règle d'impact ${missingLevelIndex + 1} doit avoir un niveau.`;
  }
  return null;
}

// ─── Hook ────────────────────────────────────────────────────────────────────

export interface ActionFormValidationParams {
  isEditMode: boolean;
  executionSteps: ExecutionStep[];
  parameterList: ParameterDefinition[];
  impactRulesList: ImpactRuleDefinition[];
}

/** Hook de validation pour ActionForm. Retourne validateForm(params) → string | null. */
export function useActionFormValidation() {
  function validateForm(params: ActionFormValidationParams): string | null {
    const { isEditMode, executionSteps, parameterList, impactRulesList } = params;

    // Validation des étapes
    if (isEditMode && executionSteps.length === 0) {
      return "Au moins une étape est requise pour enregistrer.";
    }
    if (executionSteps.length > 0) {
      for (let i = 0; i < executionSteps.length; i++) {
        const s = executionSteps[i];
        if (!s.name?.trim()) {
          return `L'étape ${i + 1} doit avoir un nom.`;
        }
        // Cas exceptionnel connecteur servicenow : validation métier — conditional_environments
        // requis pour ServiceNow — non déclaratisable (Story 83-14)
        if (s.connector_type === 'servicenow' && (!s.conditional_environments || s.conditional_environments.length === 0)) {
          return `L'étape "${s.name}" (ServiceNow) requiert au moins un environnement conditionné.`;
        }
      }
    }

    // Validation des paramètres
    const paramError = validateParameterList(parameterList);
    if (paramError) return paramError;

    // Validation des règles d'impact
    const impactError = validateImpactRulesList(impactRulesList);
    if (impactError) return impactError;

    return null;
  }

  return { validateForm };
}

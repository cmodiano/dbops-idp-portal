/**
 * useActionWizardValidation — Logique de validation extraite de ActionWizard::handleSave (Story 33.5, Task 6).
 * Factorisation avec useActionFormValidation via les helpers partagés validateParameterList,
 * validateImpactRulesList et validateChangeTypeConfig.
 */
import type {
  ChangeTypeConfigEntry,
  GateConfig,
  ImpactRuleDefinition,
  ParameterDefinition,
} from '../types/api';
import {
  validateParameterList,
  validateImpactRulesList,
  validateChangeTypeConfig,
} from './useActionFormValidation';

type IntegrationLike = { id: number; type: string; name: string } & Record<string, unknown>;

export interface ActionWizardValidationParams {
  isWorkflowSave: boolean;
  parameterList: ParameterDefinition[];
  impactRulesList: ImpactRuleDefinition[];
  changeTypeConfig: Record<string, ChangeTypeConfigEntry>;
  snIntegrationOptions: { value: number; label: string }[];
  gateConfig: GateConfig | null;
  aapTemplateId: number | undefined;
  integrationId: number | undefined;
  getIntegrationById: (id: number) => IntegrationLike | undefined;
}

interface UseActionWizardValidationParams {
  validateWorkflowSteps: () => boolean;
}

/**
 * Hook de validation pour ActionWizard.
 * Accepte validateWorkflowSteps en paramètre (dépendance sur App.useApp/modal qui reste dans le composant).
 */
export function useActionWizardValidation({ validateWorkflowSteps }: UseActionWizardValidationParams) {
  function validateForSave(params: ActionWizardValidationParams): string | null {
    const {
      isWorkflowSave,
      parameterList,
      impactRulesList,
      changeTypeConfig,
      snIntegrationOptions,
      gateConfig,
      aapTemplateId,
      integrationId,
      getIntegrationById,
    } = params;

    if (isWorkflowSave) {
      if (!validateWorkflowSteps()) {
        // validateWorkflowSteps affiche le modal d'erreur et retourne false
        return '__workflow_steps_invalid__'; // signal interne pour interrompre
      }
      return null;
    }

    // Validation des paramètres (factorisation avec ActionForm)
    const paramError = validateParameterList(parameterList);
    if (paramError) return paramError;

    // Validation des règles d'impact (factorisation)
    const impactError = validateImpactRulesList(impactRulesList);
    if (impactError) return impactError;

    // Validation changeTypeConfig + ServiceNow (factorisation)
    const changeTypeError = validateChangeTypeConfig(changeTypeConfig, snIntegrationOptions, gateConfig);
    if (changeTypeError) return changeTypeError;

    // Validation template AAP
    if (integrationId) {
      const integration = getIntegrationById(integrationId);
      const isSaveAAP = integration?.type === 'aap' || integration?.type === 'tower';
      if (isSaveAAP && (aapTemplateId == null || aapTemplateId < 1)) {
        return "Pour une intégration AAP/Tower, l'ID du template (job ou workflow) est requis.";
      }
    }

    return null;
  }

  return { validateForSave };
}

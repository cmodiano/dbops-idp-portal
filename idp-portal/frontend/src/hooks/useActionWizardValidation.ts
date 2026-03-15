/**
 * useActionWizardValidation — Logique de validation extraite de ActionWizard::handleSave (Story 33.5, Task 6).
 * Factorisation avec useActionFormValidation via les helpers partagés validateParameterList,
 * validateImpactRulesList.
 *
 * Story 83-8: Validation AAP refactorisée via platformCap + actionConfig.
 */
import type {
  ImpactRuleDefinition,
  ParameterDefinition,
} from '../types/api';
import type { PlatformCapability } from '../services/capabilities_service';
import {
  validateParameterList,
  validateImpactRulesList,
} from './useActionFormValidation';

type IntegrationLike = { id: number; type: string; name: string };

export interface ActionWizardValidationParams {
  isWorkflowSave: boolean;
  parameterList: ParameterDefinition[];
  impactRulesList: ImpactRuleDefinition[];
  /** Story 83-8: remplace aapTemplateId — platformCap + actionConfig. */
  platformCap: PlatformCapability | null;
  actionConfig: Record<string, unknown>;
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
      platformCap,
      actionConfig,
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

    // Story 83-8: Validation template AAP via platformCap + actionConfig
    if (integrationId && platformCap?.connector_type === 'aap') {
      const template_id = actionConfig?.template_id as number | undefined;
      if (!template_id || template_id < 1) {
        return "Pour une intégration AAP/Tower, l'ID du template (job ou workflow) est requis.";
      }
    } else if (integrationId && !platformCap) {
      // Fallback: vérification par integration type si platformCap pas encore chargé
      const integration = getIntegrationById(integrationId);
      const isSaveAAP = integration?.type === 'aap' || integration?.type === 'tower';
      if (isSaveAAP) {
        const template_id = actionConfig?.template_id as number | undefined;
        if (!template_id || template_id < 1) {
          return "Pour une intégration AAP/Tower, l'ID du template (job ou workflow) est requis.";
        }
      }
    }

    return null;
  }

  return { validateForSave };
}

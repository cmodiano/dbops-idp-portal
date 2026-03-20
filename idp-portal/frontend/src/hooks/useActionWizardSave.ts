/**
 * useActionWizardSave — Logique de sauvegarde extraite de ActionWizard::handleSave (Story 88-6, SMELL-FE-01).
 *
 * Suit le même pattern architectural que useActionWizardValidation.ts :
 * - Interface de paramètres exportée
 * - Hook retournant les handlers
 * - notification passé en params (pas d'App.useApp() dans le hook — évite context hors-composant)
 */
import type { FormInstance } from 'antd';
import type React from 'react';
import type {
  ActionCreate,
  ActionDetail,
  ActionResponse,
  ActionEngine,
  ParameterDefinition,
  ImpactRuleDefinition,
  ImpactLevel,
  ExecutionStep,
  ItemType,
  WorkflowStep,
  ConnectorType,
} from '../types/api';
import type { PlatformCapability } from '../services/capabilities_service';
import { parameterListToSchema } from '../utils/parametersSchema';
import { listToImpactRules } from '../utils/impactRulesSchema';
import { ApiError } from './useActionWizardState';
import type { ActionWizardValidationParams } from './useActionWizardValidation';

type IntegrationLike = { id: number; type: string; name: string };
type ValidateForSaveFn = (params: ActionWizardValidationParams) => string | null;

/** Interface minimale pour notification (issu de App.useApp() dans le composant). */
interface NotificationAPI {
  warning(args: { message: string; description?: string; duration?: number }): void;
  info(args: { message: string; description?: string }): void;
}

type Step1Ref = { integration_id?: number; engine?: string; category?: string } | null;

/** Story 83-8 — construire connector_config depuis actionConfig + platformCap. */
function buildConnectorConfig(
  platformCap: PlatformCapability | null,
  actionConfig: Record<string, unknown>,
): Record<string, unknown> | null {
  if (!platformCap || platformCap.connector_type === 'none') return null;
  if (platformCap.connector_type === 'aap') {
    const resource_type = (actionConfig.resource_type as string) ?? 'job_template';
    const template_id = actionConfig.template_id as number | undefined;
    if (!template_id || template_id < 1) return null;
    return resource_type === 'workflow_job'
      ? { resource_type: 'workflow_job' as const, workflow_job_template_id: template_id }
      : { resource_type: 'job_template' as const, job_template_id: template_id };
  }
  return Object.keys(actionConfig).length > 0 ? actionConfig : null;
}

export interface UseActionWizardSaveParams {
  form: FormInstance;
  _step1ValuesRef: React.MutableRefObject<Step1Ref>;
  setSubmitError: (msg: string | null) => void;
  setSaving: (b: boolean) => void;
  validateForSave: ValidateForSaveFn;
  parameterList: ParameterDefinition[];
  impactRulesList: ImpactRuleDefinition[];
  platformCap: PlatformCapability | null;
  actionConfig: Record<string, unknown>;
  defaultImpactLevel: ImpactLevel | null;
  outputSchemaId: number | null;
  selectedTags: string[];
  initialTags: string[];
  workflowSteps: WorkflowStep[];
  editAction: ActionDetail | null;
  onSubmit: (payload: ActionCreate) => Promise<ActionDetail | ActionResponse | void>;
  onSuccess?: (result: ActionDetail | ActionResponse) => void;
  handleUpdateActionTags: (id: number, tags: string[]) => Promise<void>;
  handleUpdateWorkflowSteps: (id: number, payload: { steps: WorkflowStep[] }) => Promise<void>;
  handleUpdateActionSteps: (id: number, payload: { steps: ExecutionStep[] }) => Promise<void>;
  getIntegrationById: (id: number) => IntegrationLike | undefined;
  notification: NotificationAPI;
}

export function useActionWizardSave(params: UseActionWizardSaveParams): {
  handleSave: () => Promise<void>;
} {
  const {
    form,
    _step1ValuesRef,
    setSubmitError,
    setSaving,
    validateForSave,
    parameterList,
    impactRulesList,
    platformCap,
    actionConfig,
    defaultImpactLevel,
    outputSchemaId,
    selectedTags,
    initialTags,
    workflowSteps,
    editAction,
    onSubmit,
    onSuccess,
    handleUpdateActionTags,
    handleUpdateWorkflowSteps,
    handleUpdateActionSteps,
    getIntegrationById,
    notification,
  } = params;

  const handleSave = async () => {
    setSubmitError(null);
    const currentItemType = form.getFieldValue('item_type') as ItemType;
    const isWorkflowSave = currentItemType === 'workflow';

    let values: { name: string; description?: string; engine?: ActionEngine; integration_id?: number; item_type: ItemType };
    try {
      values = await form.validateFields();
    } catch {
      return;
    }

    // Validation déléguée au hook useActionWizardValidation
    const validationError = validateForSave({
      isWorkflowSave,
      parameterList,
      impactRulesList,
      platformCap,
      actionConfig,
      integrationId: values.integration_id,
      getIntegrationById,
    });
    if (validationError === '__workflow_steps_invalid__') return;
    if (validationError) {
      setSubmitError(validationError);
      return;
    }

    setSaving(true);
    try {
      // Priorité: _step1ValuesRef (capturé à la nav) > values (validateFields) > form (getFieldsValue)
      const captured = _step1ValuesRef.current;
      const formValues = form.getFieldsValue();
      const integrationId = captured?.integration_id ?? values.integration_id ?? formValues.integration_id;
      const engine = captured?.engine ?? values.engine ?? formValues.engine;

      const payload: ActionCreate = {
        name: values.name,
        description: values.description,
        item_type: currentItemType,
        // impact_rules and default_impact_level apply to both actions and workflows
        impact_rules: listToImpactRules(impactRulesList),
        default_impact_level: defaultImpactLevel,
        // Règles métier et Notifications : configurées au niveau des étapes de workflow
        notification_config: null,
        business_rule_policy_id: null,
        // Story 63.9: Schéma d'output déclaré par l'admin
        output_schema_id: outputSchemaId,
        // category: both actions and workflows
        category: (captured?.category ?? (values as Record<string, unknown>).category ?? formValues.category) as string | undefined ?? null,
        // Only include engine/integration_id/parameters_schema for actions (platform derived by backend — Story 83-13)
        ...(isWorkflowSave
          ? {}
          : {
              engine,
              integration_id: integrationId,
              parameters_schema: parameterListToSchema(parameterList),
            }),
      };

      const result = await onSubmit(payload);
      const actionId = editAction?.id ?? (result as ActionDetail | ActionResponse | undefined)?.id;
      const done = (result as ActionDetail | ActionResponse) ?? editAction;

      // Story 88-2 BUG-FE-01: Ne mettre à jour les tags que si modifiés
      const tagsChanged = JSON.stringify([...selectedTags].sort()) !== JSON.stringify(initialTags);
      if (actionId && tagsChanged) {
        try {
          await handleUpdateActionTags(actionId, selectedTags);
        } catch (tagErr) {
          if (done) onSuccess?.(done);
          notification.warning({
            message: 'Tags non mis à jour',
            description: tagErr instanceof Error ? tagErr.message : "Les tags n'ont pas pu être enregistrés. L'action a bien été créée/modifiée.",
          });
          setSaving(false);
          return;
        }
      }

      if (actionId) {
        // New workflows: always save steps. Existing: only if draft or disabled
        const canEditSteps = !editAction || editAction?.status === 'draft' || editAction?.status === 'disabled';

        if (isWorkflowSave) {
          // Story 9.5: Save workflow steps (only if draft or disabled)
          if (canEditSteps) {
            try {
              await handleUpdateWorkflowSteps(actionId, { steps: workflowSteps });
            } catch (workflowErr) {
              const errorMessage = workflowErr instanceof Error ? workflowErr.message : 'Erreur lors de la sauvegarde des étapes du workflow';
              if (errorMessage.includes('WORKFLOW_LOOP') || errorMessage.toLowerCase().includes('boucle') || errorMessage.toLowerCase().includes('cycle')) {
                setSubmitError('Boucle circulaire détectée dans les étapes du workflow. Vérifiez que les actions référencées ne créent pas de cycle.');
              } else if (errorMessage.includes('brouillon') || errorMessage.includes('draft') || errorMessage.includes('désactivée')) {
                setSubmitError("Les étapes ne peuvent être modifiées que pour un workflow en brouillon ou désactivé. Le workflow a été mis à jour mais les étapes n'ont pas été modifiées.");
              } else {
                setSubmitError(errorMessage);
              }
              setSaving(false);
              return;
            }
          } else {
            // Notify user that steps were not saved
            notification.info({
              message: 'Étapes non modifiées',
              description: "Les étapes ne peuvent être modifiées que pour un workflow en brouillon ou désactivé. Les autres modifications ont été enregistrées.",
            });
          }
        } else {
          // Save execution steps for actions (only if draft or disabled)
          if (canEditSteps) {
            const connector = integrationId
              ? (platformCap?.connector_type ?? 'none')
              : 'none';
            // Story 83-8: buildConnectorConfig dérive connector_config depuis actionConfig
            const connector_config = integrationId
              ? buildConnectorConfig(platformCap, actionConfig)
              : null;
            const singleStep: ExecutionStep = {
              order: 1,
              name: 'Exécution',
              type: 'execution',
              connector_type: connector as ConnectorType,
              connector_config: connector_config ?? undefined,
              conditional_environments: null,
            };
            try {
              await handleUpdateActionSteps(actionId, { steps: [singleStep] });
            } catch (stepsErr) {
              const errorMessage = stepsErr instanceof Error ? stepsErr.message : 'Erreur lors de la sauvegarde des étapes';
              if (errorMessage.includes('brouillon') || errorMessage.includes('draft') || errorMessage.includes('désactivée')) {
                setSubmitError("Les étapes ne peuvent être modifiées que pour une action en brouillon ou désactivée. L'action a été mise à jour mais les étapes n'ont pas été modifiées.");
              } else {
                setSubmitError(errorMessage);
              }
              setSaving(false);
              return;
            }
          } else {
            // Notify user that steps were not saved
            notification.info({
              message: 'Étapes non modifiées',
              description: "Les étapes ne peuvent être modifiées que pour une action en brouillon ou désactivée. Les autres modifications ont été enregistrées.",
            });
          }
        }
      }

      if (done) onSuccess?.(done);
    } catch (err) {
      if (err instanceof ApiError && err.status === 400 && err.responseBody?.error?.details) {
        const details = err.responseBody.error.details as Record<string, string[] | string | unknown>;
        if (details && typeof details === 'object' && !Array.isArray(details)) {
          const fieldErrors = Object.entries(details).flatMap(([field, messages]) => {
            const list = Array.isArray(messages) ? messages : [String(messages ?? '')];
            return list.length ? [{ name: field, errors: list }] : [];
          });
          if (fieldErrors.length > 0) {
            form.setFields(fieldErrors);
            setSubmitError('Veuillez corriger les erreurs indiquées dans le formulaire.');
            return;
          }
        }
      }
      setSubmitError(err instanceof Error ? err.message : "Erreur lors de l'enregistrement");
    } finally {
      setSaving(false);
    }
  };

  return { handleSave };
}

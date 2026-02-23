/**
 * ActionWizard — Wizard 3 étapes pour création/édition d'action ou workflow (Story 2.22, AC #1–#5; Story 4.10 AC4; Story 9.5).
 *
 * Modèle : 1 action = 1 étape. La plateforme (step 1) définit le connecteur.
 * Étapes : (1) Général (type, nom, moteur, plateforme, tags), (2) Automatisme & Paramètres (quel job/workflow appeler + paramètres, ou étapes workflow), (3) Impact & Changement.
 *
 * Story 9.5: Support for workflows (item_type='workflow') with WorkflowStepsEditor.
 */

import { useEffect, useState } from 'react';
import { Modal, Steps, Button, Form, Alert, Space, App, List } from 'antd';
import { CloseCircleOutlined } from '@ant-design/icons';
import type {
  ActionCreate,
  ActionDetail,
  ActionResponse,
  ActionPlatform,
  ActionEngine,
  ParameterDefinition,
  ImpactRuleDefinition,
  ImpactLevel,
  ChangeTypeConfigEntry,
  ExecutionStep,
  ItemType,
  WorkflowStep,
  GateConfig,
  NotificationConfig,
} from '../../types/api';
import { schemaToParameterList, parameterListToSchema } from '../../utils/parametersSchema';
import { impactRulesToList, listToImpactRules } from '../../utils/impactRulesSchema';
import { validateWorkflowGraph } from '../../utils/workflowValidation';
import { workflowStepsToReactFlow } from '../../utils/workflowConversion';
import { ApiError } from '../../services/api_client';
// DIP: services encapsulés dans useActionWizardState — SOLID-FE-4
import { useActionWizardState } from '../../hooks/useActionWizardState';
import { useEngines } from '../../hooks/useEngines';
import { usePlatformIntegrations } from '../../hooks/usePlatformIntegrations';
import { useCategories } from '../../hooks/useCategories';
import { useServiceNowIntegrations } from '../../hooks/useServiceNowIntegrations';
import { integrationTypeToPlatformCode, integrationToConnector } from '../../utils/integrationHelpers';
import { useActionWizardValidation } from '../../hooks/useActionWizardValidation';
import { WizardStep1General } from './WizardStep1General';
import { WizardStep2Automatisme } from './WizardStep2Automatisme';
import { WizardStep3ImpactChangement } from './WizardStep3ImpactChangement';

const STEP_ITEMS = [
  { title: 'Général', content: 'Type, nom, moteur, intégration, tags' },
  { title: 'Automatisme & Paramètres', content: 'Configuration selon le type' },
  { title: 'Impact & Changement', content: 'Règles d\'impact, changement ServiceNow, règles métier' },
];

export interface ActionWizardProps {
  open: boolean;
  onCancel: () => void;
  onSubmit: (action: ActionCreate) => Promise<ActionDetail | ActionResponse | void>;
  loading?: boolean;
  error?: string | null;
  editAction?: ActionDetail | null;
  onSuccess?: (action: ActionDetail | ActionResponse) => void;
  initialItemType?: 'action' | 'workflow';
}

export function ActionWizard({
  open,
  onCancel,
  onSubmit,
  loading,
  error,
  editAction,
  onSuccess,
  initialItemType,
}: ActionWizardProps) {
  const { notification, modal } = App.useApp();
  const [form] = Form.useForm();
  const [currentStep, setCurrentStep] = useState(0);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const [parameterList, setParameterList] = useState<ParameterDefinition[]>([]);
  const [impactRulesList, setImpactRulesList] = useState<ImpactRuleDefinition[]>([]);
  const [defaultImpactLevel, setDefaultImpactLevel] = useState<ImpactLevel | null>(null);
  const [selectedTags, setSelectedTags] = useState<string[]>([]);

  // DIP: services encapsulés via useActionWizardState — SOLID-FE-4
  const {
    tagsOptions,
    handleUpdateActionTags,
    handleUpdateActionSteps,
    handleUpdateWorkflowSteps,
    handleUpdateBusinessRulePolicies,
    handlePatchAction,
  } = useActionWizardState({ open });
  const [changeTypeConfig, setChangeTypeConfig] = useState<Record<string, ChangeTypeConfigEntry>>({});
  // Story 31.6: Gate configuration (integration selection per gate type)
  const [gateConfig, setGateConfig] = useState<GateConfig | null>(null);
  // Story 31.8: Notification configuration (email, teams, page)
  const [notificationConfig, setNotificationConfig] = useState<NotificationConfig | null>(null);
  /** Story 28.4: Predefined business rule policy ID (FK). Inline rules removed — only catalogue. */
  const [businessRulePolicyId, setBusinessRulePolicyId] = useState<number | null>(null);
  /** Pour AAP : type de ressource (job_template | workflow_job) et ID template. 1 action = 1 étape. */
  const [aapResourceType, setAapResourceType] = useState<'job_template' | 'workflow_job'>('job_template');
  const [aapTemplateId, setAapTemplateId] = useState<number | undefined>(undefined);
  /** Story 9.5: Workflow steps for item_type='workflow'. */
  const [workflowSteps, setWorkflowSteps] = useState<WorkflowStep[]>([]);
  /** Story 16.5: Toggle between list and visual mode for workflow steps. */
  const [workflowViewMode, setWorkflowViewMode] = useState<'list' | 'visual'>('list');

  const isEditMode = !!editAction;
  // Read-only if editing a published action (draft and disabled actions can be edited)
  const isReadOnly = isEditMode && editAction?.status === 'published';
  const integrationId = Form.useWatch<number>('integration_id', form);
  const itemType = Form.useWatch<ItemType>('item_type', form);
  const isWorkflow = itemType === 'workflow' || (!isEditMode && initialItemType === 'workflow' && itemType == null);
  const showTypeSelector = !initialItemType && !isEditMode;

  // Story 13.7: Load engines from REF_ENGINES table
  const { engineOptions, loading: enginesLoading } = useEngines();
  // Story 31.1: Load platform integrations (replaces usePlatforms)
  const { integrationOptions, loading: integrationsLoading, getIntegrationById } = usePlatformIntegrations();
  // Story 31.6: Load ServiceNow integrations for gate config validation (AC #3)
  const { integrationOptions: snIntegrationOptions } = useServiceNowIntegrations();
  // Story 2.30: Load categories from REF_CATEGORIES table
  const { categoryOptions, loading: categoriesLoading } = useCategories();

  // Story 31.1: Derive AAP check from selected integration
  const selectedIntegration = integrationId ? getIntegrationById(integrationId) : undefined;
  const isPlatformAAP = selectedIntegration?.type === 'aap' || selectedIntegration?.type === 'tower';

  useEffect(() => {
    if (open && editAction) {
      form.setFieldsValue({
        item_type: editAction.item_type ?? 'action',
        name: editAction.name,
        description: editAction.description,
        category: editAction.category ?? undefined,
        engine: editAction.engine,
        // Story 31.1: Pre-fill integration_id from editAction
        integration_id: editAction.integration_id ?? undefined,
      });
      setParameterList(
        schemaToParameterList(editAction.parameters_schema ?? undefined).map((p, i) => ({
          ...p,
          id: p.id ?? `param-${i}-${Date.now()}`,
        }))
      );
      setImpactRulesList(impactRulesToList(editAction.impact_rules ?? undefined));
      setDefaultImpactLevel(editAction.default_impact_level ?? null);
      setSelectedTags(editAction.tags ?? []);
      setChangeTypeConfig(editAction.change_type_config ?? {});
      // Story 31.6: Load gate configuration
      setGateConfig(editAction.gate_config ?? null);
      // Story 31.8: Load notification configuration
      setNotificationConfig(editAction.notification_config ?? null);
      // Story 28.4: Load business rule policy (FK only; inline removed)
      setBusinessRulePolicyId(editAction.business_rule_policy_id ?? null);
      // Story 9.5: Load workflow steps for workflows
      if (editAction.item_type === 'workflow' && editAction.workflow_steps) {
        setWorkflowSteps(editAction.workflow_steps);
      } else {
        setWorkflowSteps([]);
      }
      const singleStep = editAction.execution_steps?.[0];
      if (singleStep?.connector_type === 'aap' && singleStep.connector_config) {
        const rt = singleStep.connector_config.resource_type as string;
        setAapResourceType(rt === 'workflow_job' ? 'workflow_job' : 'job_template');
        const tid =
          rt === 'workflow_job'
            ? singleStep.connector_config.workflow_job_template_id
            : singleStep.connector_config.job_template_id;
        setAapTemplateId(tid != null ? Number(tid) : undefined);
      } else {
        setAapResourceType('job_template');
        setAapTemplateId(undefined);
      }
      setCurrentStep(0);
    } else if (!open) {
      form.resetFields();
      setParameterList([]);
      setImpactRulesList([]);
      setDefaultImpactLevel(null);
      setSelectedTags([]);
      setChangeTypeConfig({});
      setGateConfig(null);
      setNotificationConfig(null);
      setBusinessRulePolicyId(null);
      setAapResourceType('job_template');
      setAapTemplateId(undefined);
      setWorkflowSteps([]);
      setCurrentStep(0);
      setSubmitError(null);
    }
  }, [open, editAction, form]);

  /** Validate workflow steps (used in both handleNext and handleSave) */
  const validateWorkflowSteps = (): boolean => {
    if (workflowSteps.length === 0) {
      setSubmitError('Au moins une étape est requise pour le workflow.');
      return false;
    }
    const missingAction = workflowSteps.some((s) => !s.referenced_action_id);
    if (missingAction) {
      setSubmitError('Chaque étape doit avoir une action sélectionnée.');
      return false;
    }
    // Story 16.7, AC8: Graph validation — block save on critical errors
    const { nodes, edges } = workflowStepsToReactFlow(workflowSteps);
    const graphValidation = validateWorkflowGraph(nodes, edges);
    if (!graphValidation.valid) {
      const errors = graphValidation.errors.filter((e) => e.type === 'error');
      modal.error({
        title: 'Impossible de sauvegarder le workflow',
        width: 600,
        content: (
          <>
            <p>Le workflow contient <strong>{errors.length} erreur(s)</strong> qui doivent être corrigées avant la sauvegarde.</p>
            <List
              size="small"
              dataSource={errors}
              renderItem={(error) => (
                <List.Item>
                  <CloseCircleOutlined style={{ color: '#ff4d4f', marginRight: 8 }} />
                  {error.message} {error.nodeId && `(Nœud: ${error.nodeId})`}
                </List.Item>
              )}
            />
          </>
        ),
        okText: 'Compris',
      });
      return false;
    }
    return true;
  };

  const { validateForSave } = useActionWizardValidation({ validateWorkflowSteps });

  const handleNext = async () => {
    if (currentStep === 0) {
      const fieldsToValidate = ['name', 'description'];
      // Only validate engine/integration for actions, not workflows
      if (!isWorkflow) {
        fieldsToValidate.push('engine', 'integration_id');
      }
      try {
        await form.validateFields(fieldsToValidate);
      } catch {
        return;
      }
    }
    // Step 2 validation for workflows
    if (currentStep === 1 && isWorkflow) {
      if (!validateWorkflowSteps()) {
        return;
      }
      setSubmitError(null);
    }
    setCurrentStep((s) => Math.min(s + 1, 2));
  };

  const handlePrev = () => setCurrentStep((s) => Math.max(s - 1, 0));

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

    // Validation déléguée au hook useActionWizardValidation (factorisation avec ActionForm)
    const validationError = validateForSave({
      isWorkflowSave,
      parameterList,
      impactRulesList,
      changeTypeConfig,
      snIntegrationOptions,
      gateConfig,
      aapTemplateId,
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
      const payload: ActionCreate = {
        name: values.name,
        description: values.description,
        item_type: currentItemType,
        // impact_rules and default_impact_level apply to both actions and workflows
        impact_rules: listToImpactRules(impactRulesList),
        default_impact_level: defaultImpactLevel,
        // Story 31.6: Gate configuration
        gate_config: gateConfig,
        // Story 31.8: Notification configuration
        notification_config: notificationConfig,
        // Only include engine/platform/integration_id/parameters_schema/category for actions
        ...(isWorkflowSave
          ? {}
          : {
              category: (values as Record<string, unknown>).category as string | undefined ?? null,
              engine: values.engine,
              // Story 31.1: Derive platform from integration type, send both
              integration_id: values.integration_id,
              platform: values.integration_id
                ? (integrationTypeToPlatformCode(getIntegrationById(values.integration_id)?.type ?? '') as ActionPlatform)
                : undefined,
              parameters_schema: parameterListToSchema(parameterList),
            }),
      };

      const result = await onSubmit(payload);
      const actionId = editAction?.id ?? (result as ActionDetail | ActionResponse | undefined)?.id;
      const done = (result as ActionDetail | ActionResponse) ?? editAction;

      if (actionId && selectedTags.length >= 0) {
        try {
          await handleUpdateActionTags(actionId, selectedTags);
        } catch (tagErr) {
          if (done) onSuccess?.(done);
          notification.warning({
            message: 'Tags non mis à jour',
            description: tagErr instanceof Error ? tagErr.message : 'Les tags n\'ont pas pu être enregistrés. L\'action a bien été créée/modifiée.',
          });
          setSaving(false);
          return;
        }
      }

      if (actionId) {
        // Story 28.4: Save business rule policy (predefined only)
        try {
          if (businessRulePolicyId) {
            await handleUpdateBusinessRulePolicies(actionId, null);
            await handlePatchAction(actionId, { business_rule_policy_id: businessRulePolicyId });
          } else {
            await handleUpdateBusinessRulePolicies(actionId, null);
            await handlePatchAction(actionId, { business_rule_policy_id: null });
          }
        } catch (policiesErr) {
          notification.warning({
            message: 'Règles métier non mises à jour',
            description: policiesErr instanceof Error ? policiesErr.message : 'Les règles métier n\'ont pas pu être enregistrées. L\'action a bien été créée/modifiée.',
          });
        }

        // New workflows: always save steps. Existing: only if draft or disabled
        const canEditSteps = !editAction || editAction?.status === 'draft' || editAction?.status === 'disabled';
        
        if (isWorkflowSave) {
          // Story 9.5: Save workflow steps (only if draft or disabled)
          if (canEditSteps) {
            try {
              await handleUpdateWorkflowSteps(actionId, { steps: workflowSteps });
            } catch (workflowErr) {
              // Handle WORKFLOW_LOOP error from backend
              const errorMessage = workflowErr instanceof Error ? workflowErr.message : 'Erreur lors de la sauvegarde des étapes du workflow';
              if (errorMessage.includes('WORKFLOW_LOOP') || errorMessage.toLowerCase().includes('boucle') || errorMessage.toLowerCase().includes('cycle')) {
                setSubmitError('Boucle circulaire détectée dans les étapes du workflow. Vérifiez que les actions référencées ne créent pas de cycle.');
              } else if (errorMessage.includes('brouillon') || errorMessage.includes('draft') || errorMessage.includes('désactivée')) {
                setSubmitError('Les étapes ne peuvent être modifiées que pour un workflow en brouillon ou désactivé. Le workflow a été mis à jour mais les étapes n\'ont pas été modifiées.');
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
              description: 'Les étapes ne peuvent être modifiées que pour un workflow en brouillon ou désactivé. Les autres modifications ont été enregistrées.',
            });
          }
        } else {
          // Save execution steps and change config for actions (only if draft or disabled)
          const change_type_config = Object.keys(changeTypeConfig).length > 0
            ? Object.fromEntries(
                Object.entries(changeTypeConfig).map(([env, e]) => [
                  env,
                  {
                    required: e?.required ?? false,
                    change_model_code: e?.required ? (e.change_model_code?.trim() || null) : null,
                    change_type: (e?.change_type ?? null) ? String(e.change_type).trim() || null : null,
                    template_id: (e?.template_id ?? null) ? String(e.template_id).trim() || null : null,
                    allowed: e?.allowed ?? true,
                    requires_maintenance_window: e?.requires_maintenance_window ?? false,
                    requires_approval: e?.requires_approval ?? false,
                  },
                ])
              )
            : null;
          
          if (canEditSteps) {
            // Story 31.1: Derive connector from integration type
            const connector = values.integration_id
              ? integrationToConnector(getIntegrationById(values.integration_id)?.type ?? '')
              : 'none';
            const connector_config =
              connector === 'aap' && aapTemplateId != null && aapTemplateId >= 1
                ? aapResourceType === 'workflow_job'
                  ? { resource_type: 'workflow_job' as const, workflow_job_template_id: aapTemplateId }
                  : { resource_type: 'job_template' as const, job_template_id: aapTemplateId }
                : null;
            const singleStep: ExecutionStep = {
              order: 1,
              name: 'Exécution',
              type: 'execution',
              connector_type: connector,
              connector_config: connector_config ?? undefined,
              conditional_environments: null,
            };
            try {
              await handleUpdateActionSteps(actionId, { steps: [singleStep], change_type_config });
            } catch (stepsErr) {
              const errorMessage = stepsErr instanceof Error ? stepsErr.message : 'Erreur lors de la sauvegarde des étapes';
              if (errorMessage.includes('brouillon') || errorMessage.includes('draft') || errorMessage.includes('désactivée')) {
                setSubmitError('Les étapes ne peuvent être modifiées que pour une action en brouillon ou désactivée. L\'action a été mise à jour mais les étapes n\'ont pas été modifiées.');
              } else {
                setSubmitError(errorMessage);
              }
              setSaving(false);
              return;
            }
          } else if (change_type_config !== null) {
            // Notify user that steps were not saved
            notification.info({
              message: 'Étapes non modifiées',
              description: 'Les étapes ne peuvent être modifiées que pour une action en brouillon ou désactivée. Les autres modifications ont été enregistrées.',
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
      setSubmitError(err instanceof Error ? err.message : 'Erreur lors de l\'enregistrement');
    } finally {
      setSaving(false);
    }
  };

  // Dynamic modal title based on item type (Story 2.29: initialItemType fallback, editAction.item_type for edit)
  const modalTitle = isEditMode
    ? (editAction?.item_type === 'workflow' ? 'Modifier le workflow' : 'Modifier l\'action')
    : isWorkflow
      ? 'Nouveau workflow'
      : 'Nouvelle action';

  return (
    <Modal
      title={modalTitle}
      open={open}
      onCancel={onCancel}
      footer={null}
      width={isWorkflow && workflowViewMode === 'visual' ? 1400 : 640}
      destroyOnHidden
      styles={{ body: { maxHeight: 'calc(100vh - 220px)', overflowY: 'auto' } }}
      aria-label={modalTitle}
    >
      {error && (
        <Alert title="Erreur" description={error} type="error" showIcon style={{ marginBottom: 16 }} />
      )}
      {submitError && (
        <Alert title="Erreur" description={submitError} type="error" showIcon closable onClose={() => setSubmitError(null)} style={{ marginBottom: 16 }} role="alert" />
      )}

      <Steps
        current={currentStep}
        items={STEP_ITEMS.map((item, i) => ({
          title: item.title,
          ...(item.content != null && { content: item.content }),
          status: i === currentStep ? 'process' : i < currentStep ? 'finish' : 'wait',
        }))}
        style={{ marginBottom: 24 }}
        aria-label={`Étape ${currentStep + 1} sur 3 : ${STEP_ITEMS[currentStep].title}`}
      />

      <div style={{ minHeight: 280 }}>
        <Form
          form={form}
          layout="vertical"
          initialValues={{ item_type: initialItemType ?? 'action', name: '', description: '', engine: undefined }}
        >
          <div style={{ display: currentStep === 0 ? 'block' : 'none' }}>
            <WizardStep1General
              form={form}
              isWorkflow={isWorkflow}
              showTypeSelector={showTypeSelector}
              isReadOnly={!!isReadOnly}
              engineOptions={engineOptions}
              enginesLoading={enginesLoading}
              integrationOptions={integrationOptions}
              integrationsLoading={integrationsLoading}
              isEditMode={isEditMode}
              editAction={editAction}
              selectedTags={selectedTags}
              setSelectedTags={setSelectedTags}
              tagsOptions={tagsOptions}
              categoryOptions={categoryOptions}
              categoriesLoading={categoriesLoading}
              getIntegrationById={getIntegrationById}
            />
          </div>
          {currentStep === 1 && (
            <WizardStep2Automatisme
              isWorkflow={isWorkflow}
              isReadOnly={!!isReadOnly}
              isPlatformAAP={isPlatformAAP}
              integrationId={integrationId}
              aapResourceType={aapResourceType}
              setAapResourceType={setAapResourceType}
              aapTemplateId={aapTemplateId}
              setAapTemplateId={setAapTemplateId}
              parameterList={parameterList}
              setParameterList={setParameterList}
              workflowSteps={workflowSteps}
              setWorkflowSteps={setWorkflowSteps}
              workflowViewMode={workflowViewMode}
              setWorkflowViewMode={setWorkflowViewMode}
            />
          )}
          {currentStep === 2 && (
            <WizardStep3ImpactChangement
              isWorkflow={isWorkflow}
              isReadOnly={!!isReadOnly}
              impactRulesList={impactRulesList}
              setImpactRulesList={setImpactRulesList}
              defaultImpactLevel={defaultImpactLevel}
              setDefaultImpactLevel={setDefaultImpactLevel}
              changeTypeConfig={changeTypeConfig}
              setChangeTypeConfig={setChangeTypeConfig}
              gateConfig={gateConfig}
              setGateConfig={setGateConfig}
              businessRulePolicyId={businessRulePolicyId}
              setBusinessRulePolicyId={setBusinessRulePolicyId}
              notificationConfig={notificationConfig}
              setNotificationConfig={setNotificationConfig}
              selectedIntegration={selectedIntegration}
              editAction={editAction}
              getIntegrationById={getIntegrationById}
            />
          )}
        </Form>
      </div>

      <div style={{ marginTop: 24, display: 'flex', justifyContent: 'space-between' }}>
        <Button onClick={onCancel}>Annuler</Button>
        <Space>
          {currentStep > 0 && <Button onClick={handlePrev}>Précédent</Button>}
          {currentStep < 2 && (
            <Button type="primary" onClick={handleNext}>
              Suivant
            </Button>
          )}
          {currentStep === 2 && (
            <Button type="primary" onClick={handleSave} loading={!!(loading || saving)} disabled={isReadOnly}>
              Enregistrer
            </Button>
          )}
        </Space>
      </div>
    </Modal>
  );
}

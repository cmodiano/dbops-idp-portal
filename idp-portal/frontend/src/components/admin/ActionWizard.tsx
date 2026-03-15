/**
 * ActionWizard — Wizard 3 étapes pour création/édition d'action ou workflow (Story 2.22, AC #1–#5; Story 4.10 AC4; Story 9.5).
 *
 * Modèle : 1 action = 1 étape. La plateforme (step 1) définit le connecteur.
 * Étapes : (1) Général (type, nom, moteur, plateforme, tags), (2) Automatisme & Paramètres (quel job/workflow appeler + paramètres, ou étapes workflow), (3) Impact (règles d'impact, niveau par défaut).
 *
 * Story 9.5: Support for workflows (item_type='workflow') with WorkflowStepsEditor.
 */

import { useEffect, useState, useRef, useMemo } from 'react';
import { Modal, Steps, Button, Form, Alert, Space, App, List } from 'antd';
import { CloseCircleOutlined } from '@ant-design/icons';
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
} from '../../types/api';
import { schemaToParameterList, parameterListToSchema } from '../../utils/parametersSchema';
import { impactRulesToList, listToImpactRules } from '../../utils/impactRulesSchema';
import { validateWorkflowGraph } from '../../utils/workflowValidation';
import { workflowStepsToReactFlow } from '../../utils/workflowConversion';
// DIP: services et ApiError encapsulés dans useActionWizardState — SOLID-FE-4 / Story 71.1 AC9
import { useActionWizardState, ApiError } from '../../hooks/useActionWizardState';
import { useEngines } from '../../hooks/useEngines';
import { usePlatformIntegrations } from '../../hooks/usePlatformIntegrations';
import { useCategories } from '../../hooks/useCategories';
import { useCapabilities } from '../../hooks/useCapabilities';
import type { CapabilitiesState } from '../../hooks/useCapabilities';
import type { PlatformCapability } from '../../services/capabilities_service';
import { useActionWizardValidation } from '../../hooks/useActionWizardValidation';
import { WizardStep1General } from './WizardStep1General';
import { WizardStep2Automatisme } from './WizardStep2Automatisme';
import { WizardStep3ImpactChangement } from './WizardStep3ImpactChangement';
import { OutputSchemaPanel } from './OutputSchemaPanel';

/** Story 83-8 — construire connector_config depuis actionConfig + platformCap. */
function buildConnectorConfig(
  platformCap: PlatformCapability | null,
  actionConfig: Record<string, unknown>,
): Record<string, unknown> | null {
  if (!platformCap || platformCap.connector_type === 'none') return null;
  // Cas exceptionnel connecteur aap : transformation structurelle du payload runtime
  // (template_id → job_template_id / workflow_job_template_id selon resource_type) — non déclaratisable (Story 83-14)
  if (platformCap.connector_type === 'aap') {
    const resource_type = (actionConfig.resource_type as string) ?? 'job_template';
    const template_id = actionConfig.template_id as number | undefined;
    if (!template_id || template_id < 1) return null;
    return resource_type === 'workflow_job'
      ? { resource_type: 'workflow_job' as const, workflow_job_template_id: template_id }
      : { resource_type: 'job_template' as const, job_template_id: template_id };
  }
  // Autres connecteurs : retourner action_config tel quel
  return Object.keys(actionConfig).length > 0 ? actionConfig : null;
}

/** Story 82.7 — lookup dans capabilities.platforms par code canonique.
 *  Story 83-14: le lookup par alias supprimé — integrationType est toujours un code canonique
 *  (integration.type depuis l'API, qui expose IntegrationTypeCatalogue.code). */
function getPlatformCapability(
  integrationType: string,
  capabilities: CapabilitiesState | null,
): PlatformCapability | null {
  if (!capabilities || !integrationType) return null;
  return capabilities.platforms.find((p) => p.code === integrationType) ?? null;
}

const STEP_ITEMS = [
  { title: 'Général', content: 'Type, nom, moteur, intégration, tags' },
  { title: 'Automatisme & Paramètres', content: 'Configuration selon le type' },
  { title: 'Impact', content: 'Règles d\'impact, niveau par défaut' },
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
  /** Story 63.9: Afficher le panneau OutputSchema uniquement pour les admins. */
  isAdmin?: boolean;
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
  isAdmin = false,
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
  /** Valeurs de l'étape 1 capturées à la navigation — évite la perte quand step 1 est masqué (display:none) */
  const _step1ValuesRef = useRef<{ integration_id?: number; engine?: string; category?: string } | null>(null);

  // DIP: services encapsulés via useActionWizardState — SOLID-FE-4
  const {
    tagsOptions,
    handleUpdateActionTags,
    handleUpdateActionSteps,
    handleUpdateWorkflowSteps,
  } = useActionWizardState({ open });
  /** Story 83-8: État unifié de configuration de plateforme (remplace aapResourceType + aapTemplateId). */
  const [actionConfig, setActionConfig] = useState<Record<string, unknown>>({});
  /** Story 9.5: Workflow steps for item_type='workflow'. */
  const [workflowSteps, setWorkflowSteps] = useState<WorkflowStep[]>([]);
  /** Story 16.5: Toggle between list and visual mode for workflow steps. */
  const [workflowViewMode, setWorkflowViewMode] = useState<'list' | 'visual'>('list');
  /** Story 63.9: ID du schéma d'output déclaré pour cette action (null = aucun). */
  const [outputSchemaId, setOutputSchemaId] = useState<number | null>(null);

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
  // Story 2.30: Load categories from REF_CATEGORIES table
  const { categoryOptions, loading: categoriesLoading } = useCategories();
  // Story 82.7: capacités backend pour dériver connector_type et action_platform_code
  const { capabilities } = useCapabilities();

  // Story 31.1: Derive AAP check from selected integration
  const selectedIntegration = integrationId ? getIntegrationById(integrationId) : undefined;
  // Story 82.7/82.9: lookup dans capabilities.platforms — pas de fallback (supprimé en 82.9)
  const platformCap = useMemo(
    () => getPlatformCapability(selectedIntegration?.type ?? '', capabilities),
    [selectedIntegration?.type, capabilities],
  );
  // Inclure l'intégration courante dans les options si absente (ex: statut invalid, filtrée)
  const integrationOptionsWithCurrent = useMemo(() => {
    const currentId = editAction?.integration_id ?? integrationId;
    if (!currentId || integrationOptions.some((o) => o.value === currentId)) {
      return integrationOptions;
    }
    const current = getIntegrationById(currentId);
    const label = current ? `${current.name} — ${current.type}` : `Intégration #${currentId}`;
    return [{ value: currentId, label }, ...integrationOptions];
  }, [integrationOptions, editAction?.integration_id, integrationId, getIntegrationById]);

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
      // Story 63.9: Pré-remplir output_schema_id
      setOutputSchemaId(editAction.output_schema_id ?? null);
      // Story 9.5: Load workflow steps for workflows
      if (editAction.item_type === 'workflow' && editAction.workflow_steps) {
        setWorkflowSteps(editAction.workflow_steps);
      } else {
        setWorkflowSteps([]);
      }
      // Story 83-8: pré-remplir actionConfig depuis connector_config
      const singleStep = editAction.execution_steps?.[0];
      if (singleStep?.connector_config) {
        const cfg = singleStep.connector_config;
        if (singleStep.connector_type === 'aap') {
          const resource_type = (cfg.resource_type as string) ?? 'job_template';
          const template_id = resource_type === 'workflow_job'
            ? cfg.workflow_job_template_id
            : cfg.job_template_id;
          setActionConfig({ resource_type, template_id: template_id != null ? Number(template_id) : undefined });
        } else {
          setActionConfig(cfg as Record<string, unknown>);
        }
      } else {
        setActionConfig({});
      }
      setCurrentStep(0);
      _step1ValuesRef.current = null;
    } else if (!open) {
      form.resetFields();
      _step1ValuesRef.current = null;
      setParameterList([]);
      setImpactRulesList([]);
      setDefaultImpactLevel(null);
      setSelectedTags([]);
      setActionConfig({});
      setWorkflowSteps([]);
      setOutputSchemaId(null);
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
    // Story 57.13: Only platform steps require referenced_action_id; gate/evaluation/etc. have their own requirements
    const missingAction = workflowSteps.some((s) => {
      const stepType = s.step_type ?? 'platform';
      return stepType === 'platform' && !s.referenced_action_id;
    });
    if (missingAction) {
      setSubmitError('Chaque étape de type "Exécuter" doit avoir une action sélectionnée.');
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
      // Capturer les valeurs de l'étape 1 avant de masquer (évite perte integration_id, engine, etc.)
      const vals = form.getFieldsValue();
      _step1ValuesRef.current = {
        integration_id: vals.integration_id,
        engine: vals.engine,
        category: vals.category,
      };
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

  const handlePrev = () => {
    if (currentStep === 1) _step1ValuesRef.current = null;
    setCurrentStep((s) => Math.max(s - 1, 0));
  };

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
        // Règles métier et Notifications : configurées au niveau des étapes de workflow (EvaluationStepConfig, service_call)
        notification_config: null,
        business_rule_policy_id: null,
        // Story 63.9: Schéma d'output déclaré par l'admin
        output_schema_id: outputSchemaId,
        // category: both actions and workflows (workflows: optional, backend defaults to 'autres')
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
                setSubmitError('Les étapes ne peuvent être modifiées que pour une action en brouillon ou désactivée. L\'action a été mise à jour mais les étapes n\'ont pas été modifiées.');
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
              integrationOptions={integrationOptionsWithCurrent}
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
              platformCap={platformCap}
              integrationId={integrationId}
              actionConfig={actionConfig}
              setActionConfig={setActionConfig}
              parameterList={parameterList}
              setParameterList={setParameterList}
              workflowSteps={workflowSteps}
              setWorkflowSteps={setWorkflowSteps}
              workflowViewMode={workflowViewMode}
              setWorkflowViewMode={setWorkflowViewMode}
              workflowId={editAction?.id}
            />
          )}
          {currentStep === 2 && (
            <>
              <WizardStep3ImpactChangement
                isWorkflow={isWorkflow}
                isReadOnly={!!isReadOnly}
                impactRulesList={impactRulesList}
                setImpactRulesList={setImpactRulesList}
                defaultImpactLevel={defaultImpactLevel}
                setDefaultImpactLevel={setDefaultImpactLevel}
              />
              {/* Story 63.9: Schéma d'output — visible uniquement pour les actions admin */}
              {!isWorkflow && (
                <div style={{ marginTop: 16 }}>
                  <OutputSchemaPanel
                    value={outputSchemaId}
                    onChange={setOutputSchemaId}
                    isAdmin={isAdmin}
                    disabled={!!isReadOnly}
                  />
                </div>
              )}
            </>
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

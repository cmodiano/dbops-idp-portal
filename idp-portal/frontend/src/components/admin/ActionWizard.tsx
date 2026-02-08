/**
 * ActionWizard — Wizard 3 étapes pour création/édition d'action ou workflow (Story 2.22, AC #1–#5; Story 4.10 AC4; Story 9.5).
 *
 * Modèle : 1 action = 1 étape. La plateforme (step 1) définit le connecteur.
 * Étapes : (1) Général (type, nom, moteur, plateforme, tags), (2) Automatisme & Paramètres (quel job/workflow appeler + paramètres, ou étapes workflow), (3) Impact & Changement.
 *
 * Story 9.5: Support for workflows (item_type='workflow') with WorkflowStepsEditor.
 */

import { useEffect, useState } from 'react';
import { Modal, Steps, Button, Form, Input, Select, Alert, Space, App, Radio, List } from 'antd';
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
  ConnectorType,
  ItemType,
  WorkflowStep,
} from '../../types/api';
import { schemaToParameterList, parameterListToSchema } from '../../utils/parametersSchema';
import { impactRulesToList, listToImpactRules } from '../../utils/impactRulesSchema';
import { ParametersEditor } from './ParametersEditor';
import { ImpactRulesEditor } from './ImpactRulesEditor';
import { ChangeTypeConfig } from './ChangeTypeConfig';
import { WorkflowStepsEditor } from './WorkflowStepsEditor';
import { WorkflowBuilderCanvas, validateWorkflowGraph, workflowStepsToReactFlow } from './WorkflowBuilderCanvas';
import { getTags, updateActionTags, updateActionSteps, updateWorkflowSteps, checkActionNameAvailable } from '../../services/admin_service';
import { useEngines } from '../../hooks/useEngines';
import { usePlatforms } from '../../hooks/usePlatforms';
import { useCategories } from '../../hooks/useCategories';

const { TextArea } = Input;

/** Plateforme (step 1) définit le connecteur. 1 action = 1 step. */
function platformToConnector(platform: ActionPlatform): ConnectorType {
  const map: Record<ActionPlatform, ConnectorType> = {
    AAP: 'aap',
    'GitHub Actions': 'github_actions',
    'Azure DevOps': 'azuredevops',
    Terraform: 'terraform',
  };
  return map[platform] ?? 'none';
}

const STEP_ITEMS = [
  { title: 'Général', content: 'Type, nom, moteur, plateforme, tags' },
  { title: 'Automatisme & Paramètres', content: 'Configuration selon le type' },
  { title: 'Impact & Changement', content: 'Règles d\'impact et code modèle' },
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
  const { notification } = App.useApp();
  const [form] = Form.useForm();
  const [currentStep, setCurrentStep] = useState(0);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const [parameterList, setParameterList] = useState<ParameterDefinition[]>([]);
  const [impactRulesList, setImpactRulesList] = useState<ImpactRuleDefinition[]>([]);
  const [defaultImpactLevel, setDefaultImpactLevel] = useState<ImpactLevel | null>(null);
  const [selectedTags, setSelectedTags] = useState<string[]>([]);
  const [tagsOptions, setTagsOptions] = useState<{ value: string; label: string }[]>([]);
  const [changeTypeConfig, setChangeTypeConfig] = useState<Record<string, ChangeTypeConfigEntry>>({});
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
  const platform = Form.useWatch<ActionPlatform>('platform', form);
  const itemType = Form.useWatch<ItemType>('item_type', form);
  const isPlatformAAP = platform === 'AAP';
  const isWorkflow = itemType === 'workflow' || (!isEditMode && initialItemType === 'workflow' && itemType == null);
  const showTypeSelector = !initialItemType && !isEditMode;

  // Story 13.7: Load engines from REF_ENGINES table
  const { engineOptions, loading: enginesLoading } = useEngines();
  // Story 13.7: Load platforms from REF_PLATFORMS table
  const { platformOptions, loading: platformsLoading } = usePlatforms();
  // Story 2.30: Load categories from REF_CATEGORIES table
  const { categoryOptions, loading: categoriesLoading } = useCategories();

  useEffect(() => {
    if (!open) return;
    getTags()
      .then((list) => setTagsOptions(list.map((t) => ({ value: t.name, label: t.name }))))
      .catch(() => setTagsOptions([]));
  }, [open]);

  useEffect(() => {
    if (open && editAction) {
      form.setFieldsValue({
        item_type: editAction.item_type ?? 'action',
        name: editAction.name,
        description: editAction.description,
        category: editAction.category ?? undefined,
        engine: editAction.engine,
        platform: editAction.platform,
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
      Modal.error({
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

  const handleNext = async () => {
    if (currentStep === 0) {
      const fieldsToValidate = ['name', 'description'];
      // Only validate engine/platform for actions, not workflows
      if (!isWorkflow) {
        fieldsToValidate.push('engine', 'platform');
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

    let values: { name: string; description?: string; engine?: ActionEngine; platform?: ActionPlatform; item_type: ItemType };
    try {
      values = await form.validateFields();
    } catch {
      return;
    }

    // Validation for actions (not workflows)
    if (!isWorkflowSave) {
      if (parameterList.length > 0) {
        const names = parameterList.map((p) => (p.name ?? '').trim());
        const emptyIndex = names.findIndex((n) => !n);
        if (emptyIndex >= 0) {
          setSubmitError(`Le paramètre ${emptyIndex + 1} doit avoir un nom.`);
          return;
        }
        const seen = new Set<string>();
        for (let i = 0; i < names.length; i++) {
          if (seen.has(names[i])) {
            setSubmitError(`Deux paramètres ont le même nom "${names[i]}". Chaque nom doit être unique.`);
            return;
          }
          seen.add(names[i]);
        }
      }

      if (impactRulesList.length > 0) {
        const envs = impactRulesList.map((r) => (r.environment ?? '').trim());
        const emptyEnvIndex = envs.findIndex((e) => !e);
        if (emptyEnvIndex >= 0) {
          setSubmitError(`La règle d'impact ${emptyEnvIndex + 1} doit avoir un environnement.`);
          return;
        }
        const seenEnvs = new Set<string>();
        for (let i = 0; i < envs.length; i++) {
          if (seenEnvs.has(envs[i])) {
            setSubmitError(`Deux règles d'impact utilisent l'environnement "${envs[i]}". Chaque environnement doit être unique.`);
            return;
          }
          seenEnvs.add(envs[i]);
        }
        const missingLevelIndex = impactRulesList.findIndex((r) => !r.level);
        if (missingLevelIndex >= 0) {
          setSubmitError(`La règle d'impact ${missingLevelIndex + 1} doit avoir un niveau.`);
          return;
        }
      }

      if (values.platform === 'AAP' && (aapTemplateId == null || aapTemplateId < 1)) {
        setSubmitError('Pour la plateforme AAP, l\'ID du template (job ou workflow) est requis.');
        return;
      }
    } else {
      // Validation for workflows
      if (!validateWorkflowSteps()) {
        return;
      }
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
        // Only include engine/platform/parameters_schema/category for actions
        ...(isWorkflowSave
          ? {}
          : {
              category: (values as Record<string, unknown>).category as string | undefined ?? null,
              engine: values.engine,
              platform: values.platform,
              parameters_schema: parameterListToSchema(parameterList),
            }),
      };

      const result = await onSubmit(payload);
      const actionId = editAction?.id ?? (result as ActionDetail | ActionResponse | undefined)?.id;
      const done = (result as ActionDetail | ActionResponse) ?? editAction;

      if (actionId && selectedTags.length >= 0) {
        try {
          await updateActionTags(actionId, { tag_names: selectedTags });
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
              await updateWorkflowSteps(actionId, { steps: workflowSteps });
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
                  { required: e?.required ?? false, change_model_code: e?.required ? (e.change_model_code?.trim() || null) : null },
                ])
              )
            : null;
          
          if (canEditSteps) {
            const connector = platformToConnector(values.platform!);
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
              await updateActionSteps(actionId, { steps: [singleStep], change_type_config });
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
      setSubmitError(err instanceof Error ? err.message : 'Erreur lors de l\'enregistrement');
    } finally {
      setSaving(false);
    }
  };

  const stepContent = () => {
    return (
      <Form
        form={form}
        layout="vertical"
        initialValues={{ item_type: initialItemType ?? 'action', name: '', description: '', engine: undefined, platform: undefined }}
      >
        <div style={{ display: currentStep === 0 ? 'block' : 'none' }}>
          {/* Story 9.5 / 2.29: Type selector — hidden when initialItemType is set or in edit mode */}
          <Form.Item
            name="item_type"
            label="Type"
            rules={showTypeSelector ? [{ required: true, message: 'Le type est requis' }] : undefined}
            hidden={!showTypeSelector}
          >
            <Radio.Group aria-label="Type d'élément" disabled={isReadOnly}>
              <Radio value="action">Action</Radio>
              <Radio value="workflow">Workflow</Radio>
            </Radio.Group>
          </Form.Item>
          <Form.Item
            name="name"
            label={isWorkflow ? 'Nom du workflow' : 'Nom de l\'action'}
            validateTrigger={['onBlur', 'onFinish']}
            rules={[
              { required: true, message: 'Le nom est requis' },
              { min: 1, max: 255, message: 'Le nom doit faire entre 1 et 255 caractères' },
              {
                validator: async (_, value) => {
                  const name = value ? String(value).trim() : '';
                  if (!name) return;
                  const available = await checkActionNameAvailable(name, editAction?.id);
                  if (!available) {
                    return Promise.reject(new Error('Une action ou un workflow avec ce nom existe déjà.'));
                  }
                },
              },
            ]}
          >
            <Input placeholder={isWorkflow ? 'Ex: Provisionner environnement' : 'Ex: Créer PDB Oracle'} aria-label={isWorkflow ? 'Nom du workflow' : 'Nom de l\'action'} disabled={isReadOnly} />
          </Form.Item>
          <Form.Item name="description" label="Description" rules={[{ required: true, message: 'La description est requise' }, { max: 4000, message: 'La description ne peut pas dépasser 4000 caractères' }]}>
            <TextArea rows={3} placeholder="Description..." aria-label="Description" showCount maxLength={4000} disabled={isReadOnly} />
          </Form.Item>
          {/* Story 2.30: Category field for actions only (not workflows) */}
          {!isWorkflow && (
            <Form.Item
              name="category"
              label="Catégorie"
              rules={[{ required: false }]}
              tooltip="La catégorie permet d'organiser les actions dans le catalogue"
            >
              <Select
                options={categoryOptions}
                placeholder={categoriesLoading ? "Chargement..." : "Sélectionnez une catégorie"}
                loading={categoriesLoading}
                disabled={isReadOnly}
                allowClear
                aria-label="Catégorie"
              />
            </Form.Item>
          )}
          {/* Only show engine/platform for actions, not workflows */}
          {!isWorkflow && (
            <>
              <Form.Item name="engine" label="Moteur de base de données" rules={[{ required: true, message: 'Le moteur est requis' }]}>
                <Select 
                  options={engineOptions} 
                  placeholder={enginesLoading ? "Chargement..." : "Sélectionnez un moteur"} 
                  aria-label="Moteur"
                  loading={enginesLoading}
                  disabled={isReadOnly}
                />
              </Form.Item>
              <Form.Item name="platform" label="Plateforme d'exécution" rules={[{ required: true, message: 'La plateforme est requise' }]}>
                <Select 
                  options={platformOptions} 
                  placeholder={platformsLoading ? "Chargement..." : "Sélectionnez une plateforme"} 
                  aria-label="Plateforme"
                  loading={platformsLoading}
                  disabled={isReadOnly}
                />
              </Form.Item>
            </>
          )}
          <Form.Item label="Tags" tooltip="Tags existants ou saisie libre + Entrée pour en créer un nouveau.">
            <Select
              mode="tags"
              value={selectedTags}
              onChange={(v) => setSelectedTags((Array.isArray(v) ? v : [v]).filter(Boolean) as string[])}
              options={tagsOptions}
              placeholder="Ex: RAC, dataguard, provisioning"
              aria-label="Tags"
              style={{ width: '100%' }}
              tokenSeparators={[',']}
              disabled={isReadOnly}
            />
          </Form.Item>
        </div>
        {currentStep === 1 && (
          <Space orientation="vertical" style={{ width: '100%' }} size="middle">
            {/* Story 9.5 / 16.5: Show WorkflowStepsEditor or WorkflowBuilderCanvas for workflows */}
            {isWorkflow ? (
              <Form.Item label="Étapes du workflow" tooltip="Définissez les actions qui composent ce workflow, dans l'ordre d'exécution.">
                <Space direction="vertical" style={{ width: '100%' }}>
                  <Radio.Group
                    value={workflowViewMode}
                    onChange={(e) => setWorkflowViewMode(e.target.value)}
                    size="small"
                    aria-label="Mode d'édition du workflow"
                  >
                    <Radio.Button value="list">Mode liste</Radio.Button>
                    <Radio.Button value="visual">Mode visuel</Radio.Button>
                  </Radio.Group>
                  {workflowViewMode === 'list' ? (
                    <WorkflowStepsEditor
                      steps={workflowSteps}
                      onChange={setWorkflowSteps}
                      loading={false}
                      disabled={isReadOnly}
                    />
                  ) : (
                    <WorkflowBuilderCanvas
                      steps={workflowSteps}
                      onChange={setWorkflowSteps}
                      disabled={isReadOnly}
                    />
                  )}
                </Space>
              </Form.Item>
            ) : (
              <>
                {isPlatformAAP && (
                  <>
                    <Form.Item label="Quel automatisme appeler ?" style={{ marginBottom: 0 }}>
                      <Space wrap>
                        <Form.Item label="Type de ressource" style={{ marginBottom: 0 }}>
                          <Select
                            value={aapResourceType}
                            onChange={setAapResourceType}
                            options={[
                              { value: 'job_template', label: 'Job template' },
                              { value: 'workflow_job', label: 'Workflow job' },
                            ]}
                            style={{ width: 160 }}
                            aria-label="Type ressource AAP"
                            disabled={isReadOnly}
                          />
                        </Form.Item>
                        <Form.Item
                          label="ID template"
                          required
                          validateStatus={isPlatformAAP && (aapTemplateId == null || aapTemplateId < 1) ? 'error' : ''}
                          help={isPlatformAAP && (aapTemplateId == null || aapTemplateId < 1) ? 'ID du job template ou workflow job template AAP' : ''}
                          style={{ marginBottom: 0 }}
                        >
                          <Input
                            type="number"
                            min={1}
                            value={aapTemplateId ?? ''}
                            onChange={(e) => setAapTemplateId(e.target.value ? Number(e.target.value) : undefined)}
                            placeholder="ID template AAP"
                            style={{ width: 120 }}
                            aria-label="ID template AAP"
                            disabled={isReadOnly}
                          />
                        </Form.Item>
                      </Space>
                    </Form.Item>
                  </>
                )}
                <Form.Item label="Paramètres" tooltip="Définissez les paramètres de l'action (extra_vars, etc.).">
                  {/* TODO: Add disabled prop to ParametersEditor */}
                  <ParametersEditor value={parameterList} onChange={isReadOnly ? () => {} : setParameterList} />
                </Form.Item>
              </>
            )}
          </Space>
        )}
        {currentStep === 2 && (
          <Space orientation="vertical" style={{ width: '100%' }} size="middle">
            {/* Impact rules and change config for both actions and workflows */}
            <Form.Item label="Règles d'impact" tooltip="Définissez les règles d'impact par environnement.">
              {/* TODO: Add disabled prop to ImpactRulesEditor */}
              <ImpactRulesEditor value={impactRulesList} onChange={isReadOnly ? () => {} : setImpactRulesList} />
            </Form.Item>
            <Form.Item label="Niveau d'impact par défaut" tooltip="Niveau appliqué quand aucune règle ne correspond à l'environnement.">
              <Select
                value={defaultImpactLevel ?? undefined}
                onChange={(v) => setDefaultImpactLevel(v || null)}
                allowClear
                placeholder="Sélectionnez un niveau par défaut"
                style={{ width: 220 }}
                aria-label="Niveau d'impact par défaut"
                disabled={isReadOnly}
                options={[
                  { value: 'low', label: 'Faible (vert)' },
                  { value: 'medium', label: 'Moyen (orange)' },
                  { value: 'high', label: 'Élevé (rouge)' },
                  { value: 'critical', label: 'Critique (rouge foncé)' },
                ]}
              />
            </Form.Item>
            {/* Only show change config for actions, not workflows */}
            {!isWorkflow && (
              <Form.Item
                label="Changement ServiceNow par environnement"
                tooltip="Pour chaque environnement : activer « Changement requis » et, si actif, saisir le code modèle (alphanumérique, max 50). Story 2.24."
              >
                {/* TODO: Add disabled prop to ChangeTypeConfig */}
                <ChangeTypeConfig value={changeTypeConfig} onChange={isReadOnly ? () => {} : setChangeTypeConfig} />
              </Form.Item>
            )}
          </Space>
        )}
      </Form>
    );
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

      <div style={{ minHeight: 280 }}>{stepContent()}</div>

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

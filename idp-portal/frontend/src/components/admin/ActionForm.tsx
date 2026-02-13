/**
 * ActionForm component for creating/editing catalog actions (Story 2.1, AC #1, #6; Story 2.2, AC #1, #2, #3; Story 2.5; Story 3.4).
 *
 * Features:
 * - Inline validation (AC #6)
 * - JSON validation for schema and impact_rules
 * - Execution steps editor (Story 2.2, AC #1, #2)
 * - Change type config (Story 2.2, AC #3)
 * - Real-time preview with split view layout (Story 2.5, AC #1, #3)
 * - Documentation Markdown editor (Story 3.4)
 * - Accessibility: aria-labels, focus management, aria-live preview
 */

import { useEffect, useRef, useState, useMemo } from 'react';
import { Form, Input, Select, Modal, Alert, Collapse, Typography, Row, Col } from 'antd';
import { useMediaQuery } from '../../hooks/useMediaQuery';
import type {
  ActionCreate,
  ActionEngine,
  ActionPlatform,
  ActionDetail,
  ActionResponse,
  ExecutionStep,
  ChangeTypeConfigEntry,
  ActionPreviewData,
  ImpactLevel,
  ParameterDefinition,
  ImpactRuleDefinition,
  RemediationRule,
} from '../../types/api';
import { schemaToParameterList, parameterListToSchema } from '../../utils/parametersSchema';
import { impactRulesToList, listToImpactRules } from '../../utils/impactRulesSchema';
import { useEngines } from '../../hooks/useEngines';
import { usePlatforms } from '../../hooks/usePlatforms';
import { StepsEditor } from './StepsEditor';
import { ParametersEditor } from './ParametersEditor';
import { ImpactRulesEditor } from './ImpactRulesEditor';
import { ChangeTypeConfig } from './ChangeTypeConfig';
import { RemediationRulesEditor, type RemediationRuleDefinition } from './RemediationRulesEditor';
import { AdminPreview } from './AdminPreview';
import { updateActionSteps, getTags, updateActionTags, updateRemediationRules, checkActionNameAvailable } from '../../services/admin_service';

const { Text } = Typography;

const { TextArea } = Input;

interface ActionFormValues extends ActionCreate {
  execution_steps?: ExecutionStep[];
  change_type_config?: Record<string, ChangeTypeConfigEntry>;
  documentation_md?: string | null;
}

interface ActionFormProps {
  open: boolean;
  onCancel: () => void;
  onSubmit: (action: ActionCreate) => Promise<ActionDetail | ActionResponse | void>;
  loading?: boolean;
  error?: string | null;
  /** If provided, form is in edit mode for existing action (steps-only save) */
  editAction?: ActionDetail | null;
  /** Called after create+steps or edit steps succeed; parent typically closes modal and refreshes */
  onSuccess?: (action: ActionDetail | ActionResponse) => void;
}

export function ActionForm({ open, onCancel, onSubmit, loading, error, editAction, onSuccess }: ActionFormProps) {
  const [form] = Form.useForm<ActionFormValues>();
  const nameInputRef = useRef<HTMLInputElement>(null);
  const [stepsError, setStepsError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [executionSteps, setExecutionSteps] = useState<ExecutionStep[]>([]);
  const [changeTypeConfig, setChangeTypeConfig] = useState<Record<string, ChangeTypeConfigEntry>>({});
  const [parameterList, setParameterList] = useState<ParameterDefinition[]>([]);
  const [impactRulesList, setImpactRulesList] = useState<ImpactRuleDefinition[]>([]);
  const [defaultImpactLevel, setDefaultImpactLevel] = useState<ImpactLevel | null>(null);
  const [previewEnvironment, setPreviewEnvironment] = useState<string | null>(null);
  const [selectedTags, setSelectedTags] = useState<string[]>([]);
  const [tagsOptions, setTagsOptions] = useState<{ value: string; label: string }[]>([]);
  const [remediationRules, setRemediationRules] = useState<RemediationRuleDefinition[]>([]);
  
  // Story 13.7: Load engines from REF_ENGINES table
  const { engineOptions, loading: enginesLoading } = useEngines();
  // Story 13.7: Load platforms from REF_PLATFORMS table
  const { platformOptions, loading: platformsLoading } = usePlatforms();

  const isEditMode = !!editAction;
  const isMin1280 = useMediaQuery(1280);

  // Story 2.5: Real-time preview using Form.useWatch
  const watchedName = Form.useWatch('name', form);
  const watchedDescription = Form.useWatch('description', form);
  const watchedEngine = Form.useWatch('engine', form);
  const watchedPlatform = Form.useWatch('platform', form);
  const watchedDocumentationMd = Form.useWatch('documentation_md', form);

  // Load tags for autocomplete when modal opens (Story 2.6, AC #1)
  useEffect(() => {
    if (!open) return;
    getTags()
      .then((list) => setTagsOptions(list.map((t) => ({ value: t.name, label: t.name }))))
      .catch(() => setTagsOptions([]));
  }, [open]);

  // Transform form values to ActionPreviewData for preview (Story 2.17: parameters from visual editor list; Story 2.18: impact rules from list)
  const previewData: ActionPreviewData = useMemo(() => {
    const parsedSchema = parameterListToSchema(parameterList);

    // Story 2.18 AC3/AC5: Extract impact_level from impactRulesList based on selected preview environment
    // AC5: Fall back to defaultImpactLevel when no rule matches or list is empty
    let impactLevel: ImpactLevel | null = null;
    if (impactRulesList.length > 0) {
      // If previewEnvironment is set, use that environment's rule; otherwise use first rule
      const targetEnv = previewEnvironment || impactRulesList[0]?.environment;
      const matchingRule = impactRulesList.find((r) => r.environment === targetEnv);
      if (matchingRule?.level) {
        impactLevel = matchingRule.level;
      } else {
        // No matching rule for this environment — use default
        impactLevel = defaultImpactLevel;
      }
    } else {
      // No rules defined — use default impact level (AC5)
      impactLevel = defaultImpactLevel;
    }

    return {
      name: (watchedName as string) || '',
      description: (watchedDescription as string) || null,
      engine: (watchedEngine as ActionEngine) || null,
      platform: (watchedPlatform as ActionPlatform) || null,
      impact_level: impactLevel,
      parameters_schema: parsedSchema,
      tags: selectedTags,
      documentation_md: (watchedDocumentationMd as string) || null,
    };
  }, [watchedName, watchedDescription, watchedEngine, watchedPlatform, parameterList, impactRulesList, previewEnvironment, defaultImpactLevel, selectedTags, watchedDocumentationMd]);

  // Focus on name input when modal opens (AC #7 accessibility)
  useEffect(() => {
    if (open) {
      setTimeout(() => {
        nameInputRef.current?.focus();
      }, 100);
    }
  }, [open]);

  // Reset form and steps when modal opens/closes or editAction changes
  useEffect(() => {
    if (open && editAction) {
      // Edit mode: populate form with existing values
      form.setFieldsValue({
        name: editAction.name,
        description: editAction.description,
        engine: editAction.engine,
        platform: editAction.platform,
        documentation_md: editAction.documentation_md,
      } as unknown as ActionFormValues);
      setExecutionSteps(editAction.execution_steps || []);
      setChangeTypeConfig(editAction.change_type_config ?? {});
      setParameterList(
        schemaToParameterList(editAction.parameters_schema ?? undefined).map((p, i) => ({
          ...p,
          id: p.id ?? `param-${i}-${Date.now()}`,
        }))
      );
      // Story 2.18: Load impact_rules as list for visual editor
      setImpactRulesList(impactRulesToList(editAction.impact_rules ?? undefined));
      // Story 2.18 AC5: Load default impact level
      setDefaultImpactLevel(editAction.default_impact_level ?? null);
      setPreviewEnvironment(null);
      setSelectedTags(editAction.tags ?? []);
      // Story 9.1, Task 6: Load remediation_rules
      setRemediationRules(
        (editAction.remediation_rules ?? []).map((r, i) => ({
          ...r,
          id: `rule-${i}-${Date.now()}`,
        }))
      );
    } else if (!open) {
      form.resetFields();
      setExecutionSteps([]);
      setChangeTypeConfig({});
      setParameterList([]);
      setImpactRulesList([]);
      setDefaultImpactLevel(null);
      setPreviewEnvironment(null);
      setSelectedTags([]);
      setRemediationRules([]);
      setStepsError(null);
    }
  }, [open, editAction, form]);

  const handleFinish = async (values: ActionFormValues) => {
    setStepsError(null);
    setSaving(true);
    try {
      // In edit mode, require at least one step (Task 5.3; API does not accept empty steps)
      if (isEditMode && executionSteps.length === 0) {
        setStepsError("Au moins une étape est requise pour enregistrer.");
        return;
      }
      // Validate steps when present (block submit if invalid)
      if (executionSteps.length > 0) {
        for (let i = 0; i < executionSteps.length; i++) {
          const s = executionSteps[i];
          if (!s.name?.trim()) {
            setStepsError(`L'étape ${i + 1} doit avoir un nom.`);
            return;
          }
          if (s.connector_type === 'servicenow' && (!s.conditional_environments || s.conditional_environments.length === 0)) {
            setStepsError(`L'étape "${s.name}" (ServiceNow) requiert au moins un environnement conditionné.`);
            return;
          }
        }
      }

      // Story 2.17 AC4: validate parameters before save (nom requis, noms uniques)
      if (parameterList.length > 0) {
        const names = parameterList.map((p) => (p.name ?? '').trim());
        const emptyIndex = names.findIndex((n) => !n);
        if (emptyIndex >= 0) {
          setStepsError(`Le paramètre ${emptyIndex + 1} doit avoir un nom.`);
          return;
        }
        const seen = new Set<string>();
        for (let i = 0; i < names.length; i++) {
          if (seen.has(names[i])) {
            setStepsError(`Deux paramètres ont le même nom "${names[i]}". Chaque nom doit être unique.`);
            return;
          }
          seen.add(names[i]);
        }
      }

      // Story 2.18 AC6: validate impact rules before save (environnement requis, niveau requis, environnements uniques)
      if (impactRulesList.length > 0) {
        const envs = impactRulesList.map((r) => (r.environment ?? '').trim());
        const emptyEnvIndex = envs.findIndex((e) => !e);
        if (emptyEnvIndex >= 0) {
          setStepsError(`La règle d'impact ${emptyEnvIndex + 1} doit avoir un environnement.`);
          return;
        }
        const seenEnvs = new Set<string>();
        for (let i = 0; i < envs.length; i++) {
          if (seenEnvs.has(envs[i])) {
            setStepsError(`Deux règles d'impact utilisent l'environnement "${envs[i]}". Chaque environnement doit être unique.`);
            return;
          }
          seenEnvs.add(envs[i]);
        }
        const missingLevelIndex = impactRulesList.findIndex((r) => !r.level);
        if (missingLevelIndex >= 0) {
          setStepsError(`La règle d'impact ${missingLevelIndex + 1} doit avoir un niveau.`);
          return;
        }
      }

      // Story 2.24 AC2: validate change_type_config — when required=true, change_model_code required and alphanumeric max 50
      for (const [env, entry] of Object.entries(changeTypeConfig)) {
        if (entry?.required) {
          const code = (entry.change_model_code ?? '').trim();
          if (!code) {
            setStepsError(`Le code modèle est obligatoire pour ${env} lorsque « Changement requis » est activé.`);
            return;
          }
          if (!/^[A-Za-z0-9]+$/.test(code)) {
            setStepsError(`Le code modèle pour ${env} doit être alphanumérique uniquement.`);
            return;
          }
          if (code.length > 50) {
            setStepsError(`Le code modèle pour ${env} ne peut pas dépasser 50 caractères.`);
            return;
          }
        }
      }

      const action: ActionCreate = {
        name: values.name,
        description: values.description,
        engine: values.engine,
        platform: values.platform,
        parameters_schema: parameterListToSchema(parameterList),
        impact_rules: listToImpactRules(impactRulesList),
        default_impact_level: defaultImpactLevel,
        documentation_md: values.documentation_md || null,
      };

      const result = await onSubmit(action);
      const actionId = editAction?.id ?? (result as ActionDetail | ActionResponse | undefined)?.id;

      // Story 2.24: send change_type_config when we have steps OR when we have change config (use placeholder step if no steps)
      const hasChangeTypeConfig = Object.keys(changeTypeConfig).length > 0;
      const stepsToSend =
        executionSteps.length > 0
          ? executionSteps
          : hasChangeTypeConfig
            ? [{ order: 1, name: 'Étape à configurer', type: 'prerequisite' as const, connector_type: 'none' as const, conditional_environments: null }]
            : [];
      const change_type_config =
        hasChangeTypeConfig
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

      if (actionId && (stepsToSend.length > 0 || change_type_config !== null)) {
        await updateActionSteps(actionId, {
          steps: stepsToSend,
          change_type_config,
        });
      }

      if (actionId) {
        await updateActionTags(actionId, { tag_names: selectedTags });
      }

      // Story 9.1, Task 6: Save remediation rules
      if (actionId) {
        // Convert to API format (strip internal id field)
        const rulesToSave = remediationRules.length > 0
          // eslint-disable-next-line @typescript-eslint/no-unused-vars
          ? remediationRules.map(({ id, ...rule }) => rule as RemediationRule)
          : null;
        await updateRemediationRules(actionId, rulesToSave);
      }

      const done = (result as ActionDetail | ActionResponse) ?? editAction;
      if (done) onSuccess?.(done);
    } catch (err) {
      setStepsError(err instanceof Error ? err.message : 'Erreur lors de la mise à jour des étapes');
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal
      title={isEditMode ? 'Modifier l\'action' : 'Nouvelle action'}
      open={open}
      onCancel={onCancel}
      onOk={() => form.submit()}
      okText={isEditMode ? 'Enregistrer' : 'Creer'}
      cancelText="Annuler"
      confirmLoading={!!(loading || saving)}
      width={1200}
      destroyOnHidden
      styles={{
        body: { maxHeight: 'calc(100vh - 200px)', overflowY: 'auto' },
      }}
    >
      {error && (
        <Alert
          title="Erreur"
          description={error}
          type="error"
          showIcon
          style={{ marginBottom: 16 }}
        />
      )}

      {stepsError && (
        <Alert
          title="Erreur etapes"
          description={stepsError}
          type="error"
          showIcon
          style={{ marginBottom: 16 }}
        />
      )}

      {/* Story 2.5: Split view layout - Form left (60%), Preview right (40%); stack below 1280px (AC3, Task 4.4). */}
      {/* Col 14/10 ≈ 58%/42% (closest to 60/40 on 24-grid). */}
      <Row gutter={32}>
        {/* Left column: Form */}
        <Col span={isMin1280 ? 14 : 24}>
          <Form
            form={form}
            layout="vertical"
            onFinish={handleFinish}
            validateTrigger={['onChange', 'onBlur']}
          >
            <Form.Item
              name="name"
              label="Nom de l'action"
              validateTrigger={['onBlur', 'onFinish']}
              rules={[
                { required: true, message: 'Le nom est requis' },
                { min: 1, max: 255, message: 'Le nom doit faire entre 1 et 255 caracteres' },
                {
                  validator: async (_, value) => {
                    const name = value ? String(value).trim() : '';
                    if (!name) return;
                    const available = await checkActionNameAvailable(name, editAction?.id);
                    if (!available) {
                      return Promise.reject(new Error('Une action avec ce nom existe déjà.'));
                    }
                  },
                },
              ]}
            >
              <Input
                ref={nameInputRef as never}
                placeholder="Ex: Creer PDB Oracle"
                aria-label="Nom de l'action"
              />
            </Form.Item>

            <Form.Item
              name="description"
              label="Description"
              rules={[{ required: true, message: 'La description est requise' }, { max: 4000, message: 'La description ne peut pas depasser 4000 caracteres' }]}
            >
              <TextArea
                rows={3}
                placeholder="Description de l'action..."
                aria-label="Description de l'action"
                showCount
                maxLength={4000}
              />
            </Form.Item>

            {/* Story 3.4: Documentation Markdown editor */}
            <Form.Item
              name="documentation_md"
              label="Documentation (Markdown)"
              tooltip="Documentation detaillee de l'action. Supporte le format Markdown : titres, listes, blocs de code, tableaux."
            >
              <TextArea
                rows={6}
                placeholder={`# Titre\n\nDescription detaillee...\n\n## Utilisation\n\n- Etape 1\n- Etape 2\n\n\`\`\`sql\nSELECT * FROM exemple;\n\`\`\``}
                aria-label="Documentation de l'action en Markdown"
                showCount
                maxLength={100000}
              />
            </Form.Item>

            <Form.Item
              name="engine"
              label="Moteur de base de donnees"
              rules={[{ required: true, message: 'Le moteur est requis' }]}
            >
              <Select
                options={engineOptions}
                placeholder={enginesLoading ? "Chargement..." : "Selectionnez un moteur"}
                aria-label="Moteur de base de donnees"
                loading={enginesLoading}
              />
            </Form.Item>

            <Form.Item
              name="platform"
              label="Plateforme d'execution"
              rules={[{ required: true, message: 'La plateforme est requise' }]}
            >
              <Select
                options={platformOptions}
                placeholder={platformsLoading ? "Chargement..." : "Selectionnez une plateforme"}
                aria-label="Plateforme d'execution"
                loading={platformsLoading}
              />
            </Form.Item>

            {/* Story 2.17: Parametres — editeur visuel (AC1–AC6) */}
            <Form.Item
              label="Parametres"
              tooltip="Definissez les parametres de l'action via l'editeur visuel (nom, type, requis, defaut, description)"
            >
              <ParametersEditor value={parameterList} onChange={setParameterList} />
            </Form.Item>

            {/* Story 2.18: Regles d'impact — editeur visuel (AC1–AC6) */}
            <Form.Item
              label="Regles d'impact"
              tooltip="Definissez les regles d'impact par environnement (niveau de risque et justification)"
            >
              <ImpactRulesEditor value={impactRulesList} onChange={setImpactRulesList} />
            </Form.Item>

            {/* Story 2.18 AC5: Niveau d'impact par defaut */}
            <Form.Item
              label="Niveau d'impact par defaut"
              tooltip="Niveau applique quand aucune regle ne correspond a l'environnement d'execution"
            >
              <Select
                value={defaultImpactLevel ?? undefined}
                onChange={(v) => setDefaultImpactLevel(v || null)}
                allowClear
                placeholder="Selectionnez un niveau par defaut"
                style={{ width: 220 }}
                aria-label="Niveau d'impact par defaut"
                options={[
                  { value: 'low', label: 'Faible (vert)' },
                  { value: 'medium', label: 'Moyen (orange)' },
                  { value: 'high', label: 'Eleve (rouge)' },
                  { value: 'critical', label: 'Critique (rouge fonce)' },
                ]}
              />
            </Form.Item>

            {/* Story 2.18 AC3: Selecteur d'environnement pour preview dynamique */}
            {impactRulesList.length > 1 && (
              <Form.Item
                label="Environnement de preview"
                tooltip="Selectionnez l'environnement pour voir l'impact correspondant dans la preview"
              >
                <Select
                  value={previewEnvironment ?? undefined}
                  onChange={(v) => setPreviewEnvironment(v || null)}
                  allowClear
                  placeholder="Selectionnez un environnement"
                  style={{ width: 200 }}
                  aria-label="Environnement pour la preview"
                  options={impactRulesList.map((r) => ({ value: r.environment, label: r.environment }))}
                />
              </Form.Item>
            )}

            {/* Story 2.6, AC #1, #2: Section Tags — multi-select + auto-completion, create on Enter */}
            <Form.Item
              label="Tags"
              tooltip="Tags existants ou saisie libre + Entree pour en creer un nouveau. Lowercase, sans espaces."
            >
              <Select
                mode="tags"
                value={selectedTags}
                onChange={(v) => setSelectedTags((Array.isArray(v) ? v : [v]).filter(Boolean) as string[])}
                options={tagsOptions}
                placeholder="Ex: RAC, dataguard, provisioning"
                aria-label="Tags de l'action"
                style={{ width: '100%' }}
                tokenSeparators={[',']}
              />
            </Form.Item>

            {/* Execution Steps Section (Story 2.2, AC #1, #2, #3) */}
            <Collapse
              ghost
              items={[
                {
                  key: 'execution-steps',
                  label: (
                    <Text strong>
                      Etapes d'execution et changement ServiceNow
                      {executionSteps.length > 0 && (
                        <Text type="secondary" style={{ marginLeft: 8 }}>
                          ({executionSteps.length} etape{executionSteps.length > 1 ? 's' : ''})
                        </Text>
                      )}
                    </Text>
                  ),
                  children: (
                    <>
                      <Form.Item
                        label="Etapes d'execution"
                        tooltip="Definissez les etapes d'execution de l'action (AC #1, #2)"
                        style={{ marginBottom: 16 }}
                      >
                        <StepsEditor value={executionSteps} onChange={setExecutionSteps} />
                      </Form.Item>

                      <Form.Item
                        label="Changement ServiceNow par environnement"
                        tooltip="Pour chaque environnement : activer « Changement requis » et, si actif, saisir le code modèle (alphanumérique, max 50). Story 2.24."
                        style={{ marginBottom: 16 }}
                      >
                        <ChangeTypeConfig value={changeTypeConfig} onChange={setChangeTypeConfig} />
                      </Form.Item>
                    </>
                  ),
                },
                {
                  key: 'remediation-rules',
                  label: (
                    <Text strong>
                      Règles de remédiation automatique
                      {remediationRules.length > 0 && (
                        <Text type="secondary" style={{ marginLeft: 8 }}>
                          ({remediationRules.length} règle{remediationRules.length > 1 ? 's' : ''})
                        </Text>
                      )}
                    </Text>
                  ),
                  children: (
                    <Form.Item
                      label="Règles de remédiation"
                      tooltip="Configurez des règles pour proposer des actions correctives automatiques lorsque cette action échoue (Story 9.1)."
                      style={{ marginBottom: 16 }}
                    >
                      <RemediationRulesEditor
                        value={remediationRules}
                        onChange={setRemediationRules}
                        currentActionId={editAction?.id}
                      />
                    </Form.Item>
                  ),
                },
              ]}
              style={{ marginTop: 16 }}
            />
          </Form>
        </Col>

        {/* Right column: Real-time Preview (Story 2.5, AC #1, #3, #5) */}
        <Col span={isMin1280 ? 10 : 24}>
          <AdminPreview formData={previewData} />
        </Col>
      </Row>
    </Modal>
  );
}

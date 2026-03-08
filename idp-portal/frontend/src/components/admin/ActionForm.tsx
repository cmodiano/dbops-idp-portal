/**
 * ActionForm component for creating/editing catalog actions (Story 2.1, AC #1, #6; Story 2.2, AC #1, #2, #3; Story 2.5; Story 3.4).
 *
 * Features:
 * - Inline validation (AC #6)
 * - Execution steps editor (Story 2.2, AC #1, #2)
 * - Real-time preview with split view layout (Story 2.5, AC #1, #3)
 * - Documentation Markdown editor (Story 3.4)
 * - Accessibility: aria-labels, focus management, aria-live preview
 *
 * Story 33.5: Refactored — state in useActionFormState, validation in useActionFormValidation,
 * collapse sections in ActionFormCollapseSections, impact legend in ImpactLevelsLegend.
 */

import { Form, Input, Select, Modal, Alert, Button, Space, Row, Col } from 'antd';
import { DownloadOutlined } from '@ant-design/icons';
import { useEntityExport } from '../../hooks/useEntityExport';
import { useMediaQuery } from '../../hooks/useMediaQuery';
import type {
  ActionCreate,
  ActionDetail,
  ActionResponse,
  ImpactLevel,
  RemediationRule,
} from '../../types/api';
import { parameterListToSchema } from '../../utils/parametersSchema';
import { listToImpactRules } from '../../utils/impactRulesSchema';
import { useEngines } from '../../hooks/useEngines';
import { usePlatformIntegrations } from '../../hooks/usePlatformIntegrations';
import { integrationTypeToPlatformCode } from '../../utils/integrationHelpers';
import { ParametersEditor } from './ParametersEditor';
import { ImpactRulesEditor } from './ImpactRulesEditor';
import SectionHelp from '../common/SectionHelp';
import { ImpactLevelsLegend } from './ImpactLevelsLegend';
import { ActionFormCollapseSections } from './ActionFormCollapseSections';
import { AdminPreview } from './AdminPreview';
import { ApiError } from '../../services/api_client';
import {
  updateActionSteps,
  updateActionTags,
  updateRemediationRules,
  checkActionNameAvailable,
} from '../../services/admin_service';
import { useActionFormState } from '../../hooks/useActionFormState';
import { useActionFormValidation } from '../../hooks/useActionFormValidation';

const { TextArea } = Input;

interface ActionFormValues extends ActionCreate {
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

  // Story 13.7: Load engines from REF_ENGINES table
  const { engineOptions, loading: enginesLoading } = useEngines();
  // Story 31.1: Load platform integrations
  const { integrationOptions, loading: integrationsLoading, getIntegrationById } = usePlatformIntegrations();

  const isEditMode = !!editAction;
  const isMin1280 = useMediaQuery(1280);

  // Story 64.13: Single-entity YAML export
  const { exportYaml, loading: exportLoading } = useEntityExport(
    'actions',
    editAction?.id ?? 0,
    editAction?.name ?? '',
  );

  // Story 33.5: All form state extracted to hook
  const {
    nameInputRef,
    stepsError,
    setStepsError,
    saving,
    setSaving,
    executionSteps,
    setExecutionSteps,
    parameterList,
    setParameterList,
    impactRulesList,
    setImpactRulesList,
    defaultImpactLevel,
    setDefaultImpactLevel,
    previewEnvironment,
    setPreviewEnvironment,
    selectedTags,
    setSelectedTags,
    tagsOptions,
    remediationRules,
    setRemediationRules,
    watchedIntegrationId,
    previewData,
  } = useActionFormState({ open, editAction, form, getIntegrationById });

  // Story 33.5: Validation extracted to hook
  const { validateForm } = useActionFormValidation();

  const handleFinish = async (values: ActionFormValues) => {
    setStepsError(null);
    setSaving(true);
    try {
      const validationError = validateForm({
        isEditMode,
        executionSteps,
        parameterList,
        impactRulesList,
      });
      if (validationError) {
        setStepsError(validationError);
        return;
      }

      // Story 31.1: Derive platform from integration type, send both
      const selectedIntegration = values.integration_id ? getIntegrationById(values.integration_id) : undefined;
      const rawPlatform =
        selectedIntegration?.type && String(selectedIntegration.type).trim() !== ''
          ? integrationTypeToPlatformCode(selectedIntegration.type)
          : undefined;
      const derivedPlatform =
        rawPlatform !== undefined && rawPlatform !== ''
          ? (rawPlatform as ActionCreate['platform'])
          : undefined;

      const action: ActionCreate = {
        name: values.name,
        description: values.description,
        engine: values.engine,
        integration_id: values.integration_id,
        platform: derivedPlatform,
        parameters_schema: parameterListToSchema(parameterList),
        impact_rules: listToImpactRules(impactRulesList),
        default_impact_level: defaultImpactLevel,
        documentation_md: values.documentation_md || null,
        notification_config: null,
        business_rule_policy_id: null,
      };

      const result = await onSubmit(action);
      const actionId = editAction?.id ?? (result as ActionDetail | ActionResponse | undefined)?.id;

      if (actionId && executionSteps.length > 0) {
        await updateActionSteps(actionId, { steps: executionSteps });
      }

      if (actionId) {
        await updateActionTags(actionId, { tag_names: selectedTags });
      }

      // Story 9.1, Task 6: Save remediation rules
      if (actionId) {
        const rulesToSave = remediationRules.length > 0
          ? remediationRules.map(({ id: _unused, ...rule }) => rule as RemediationRule)
          : null;
        await updateRemediationRules(actionId, rulesToSave);
      }

      const done = (result as ActionDetail | ActionResponse) ?? editAction;
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
            setStepsError('Veuillez corriger les erreurs indiquées dans le formulaire.');
            return;
          }
        }
      }
      setStepsError(err instanceof Error ? err.message : 'Erreur lors de la mise à jour des étapes');
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal
      title={isEditMode ? "Modifier l'action" : 'Nouvelle action'}
      open={open}
      onCancel={onCancel}
      okText={isEditMode ? 'Enregistrer' : 'Créer'}
      cancelText="Annuler"
      confirmLoading={!!(loading || saving)}
      width={1200}
      destroyOnHidden
      styles={{
        body: { maxHeight: 'calc(100vh - 200px)', overflowY: 'auto' },
      }}
      footer={(_, { OkBtn, CancelBtn }) => (
        <Space style={{ width: '100%', justifyContent: 'space-between' }}>
          {isEditMode ? (
            <Button
              icon={<DownloadOutlined />}
              onClick={exportYaml}
              loading={exportLoading}
            >
              Exporter en YAML
            </Button>
          ) : <span />}
          <Space>
            <CancelBtn />
            <OkBtn />
          </Space>
        </Space>
      )}
      onOk={() => form.submit()}
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

      {/* Story 2.5: Split view layout - Form left (60%), Preview right (40%); stack below 1280px */}
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
              rules={[
                { required: true, message: 'La description est requise' },
                { max: 4000, message: 'La description ne peut pas depasser 4000 caracteres' },
              ]}
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
                placeholder={enginesLoading ? 'Chargement...' : 'Selectionnez un moteur'}
                aria-label="Moteur de base de donnees"
                loading={enginesLoading}
              />
            </Form.Item>

            <Form.Item
              name="integration_id"
              label={<span>Intégration <SectionHelp topicId="action-form-integration" /></span>}
              rules={[{ required: true, message: "L'intégration est requise" }]}
            >
              <Select
                options={integrationOptions}
                placeholder={integrationsLoading ? 'Chargement...' : 'Sélectionnez une intégration'}
                aria-label="Intégration"
                loading={integrationsLoading}
              />
            </Form.Item>

            {/* Story 31.1 AC4: Alert when no platform integrations available */}
            {!integrationsLoading && integrationOptions.length === 0 && (
              <Alert
                type="warning"
                showIcon
                title="Aucune intégration de type plateforme n'est disponible. Créez-en une dans Admin > Intégrations."
                style={{ marginBottom: 16 }}
              />
            )}
            {/* Story 31.1 AC6: Degraded mode for legacy actions without integration_id */}
            {isEditMode && !editAction?.integration_id && editAction?.platform && (
              <Alert
                type="info"
                showIcon
                title={`Cette action utilise l'ancienne plateforme « ${editAction.platform} ». Sélectionnez une intégration pour la mettre à jour.`}
                style={{ marginBottom: 16 }}
              />
            )}

            {/* Story 2.17: Parametres — editeur visuel */}
            <Form.Item
              label="Parametres"
              tooltip="Definissez les parametres de l'action via l'editeur visuel (nom, type, requis, defaut, description)"
            >
              <ParametersEditor value={parameterList} onChange={setParameterList} />
            </Form.Item>

            {/* Story 2.18: Regles d'impact — editeur visuel */}
            <Form.Item
              label="Regles d'impact"
              tooltip="Definissez les regles d'impact par environnement (niveau de risque et justification)"
            >
              <div style={{ width: '100%' }}>
                <ImpactLevelsLegend />
                <ImpactRulesEditor value={impactRulesList} onChange={setImpactRulesList} />
              </div>
            </Form.Item>

            {/* Story 2.18 AC5: Niveau d'impact par defaut */}
            <Form.Item
              label="Niveau d'impact par defaut"
              tooltip="Niveau applique quand aucune regle ne correspond a l'environnement d'execution"
            >
              <Select
                value={defaultImpactLevel ?? undefined}
                onChange={(v) => setDefaultImpactLevel((v || null) as ImpactLevel | null)}
                allowClear
                placeholder="Selectionnez un niveau par defaut"
                style={{ width: 220 }}
                aria-label="Niveau d'impact par defaut"
                options={[
                  { value: 'low', label: 'Faible (vert)' },
                  { value: 'medium', label: 'Moyen (orange)' },
                  { value: 'high', label: 'Élevé (rouge)' },
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

            {/* Story 2.6: Section Tags */}
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

            {/* Story 33.5 Task 4: Sections avancées extraites en composant */}
            <ActionFormCollapseSections
              executionSteps={executionSteps}
              setExecutionSteps={setExecutionSteps}
              remediationRules={remediationRules}
              setRemediationRules={setRemediationRules}
              editAction={editAction}
              watchedIntegrationId={watchedIntegrationId}
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

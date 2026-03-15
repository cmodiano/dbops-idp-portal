/**
 * WizardStep2Automatisme — Étape 2 du wizard (Automatisme & Paramètres) extraite de ActionWizard (Story 33.5, Task 5).
 * Contient : WorkflowStepsEditor ou (WizardAAPTemplateSection + ParametersEditor) selon le type.
 * Note : WizardAAPTemplateSection est co-localisé ici car utilisé exclusivement dans cette étape.
 *
 * Story 83-8: Rendu déclaratif via action_config_schema.
 *   - Schéma vide → rien rendu pour la config plateforme.
 *   - connector_type === 'aap' + schéma non vide → WizardAAPTemplateSection (renderer UX exceptionnel).
 *   - Autre connector + schéma non vide → SchemaFormRenderer générique.
 */
import { useState } from 'react';
import { Form, Input, Select, Alert, Space, Radio } from 'antd';
import type {
  ParameterDefinition,
  WorkflowStep,
} from '../../types/api';
import type { PlatformCapability } from '../../services/capabilities_service';
import { ParametersEditor } from './ParametersEditor';
import { WorkflowStepsEditor } from './WorkflowStepsEditor';
import { WorkflowBuilderCanvas } from './WorkflowBuilderCanvas';
import { SchemaFormRenderer } from '../shared';
import { useAAPTemplates } from '../../hooks/useAAPTemplates';
import { useDebounce } from '../../hooks/useDebounce';

// ─── WizardAAPTemplateSection (composant local, non exporté) ─────────────────

interface WizardAAPTemplateSectionProps {
  integrationId: number | undefined;
  actionConfig: Record<string, unknown>;
  onActionConfigChange: (v: Record<string, unknown>) => void;
  isReadOnly: boolean;
}

function WizardAAPTemplateSection({
  integrationId,
  actionConfig,
  onActionConfigChange,
  isReadOnly,
}: WizardAAPTemplateSectionProps) {
  const [searchInput, setSearchInput] = useState('');
  const debouncedSearch = useDebounce(searchInput, 300);

  const aapResourceType = (actionConfig.resource_type as 'job_template' | 'workflow_job') ?? 'job_template';
  const aapTemplateId = actionConfig.template_id as number | undefined;

  const handleResourceTypeChange = (v: 'job_template' | 'workflow_job') => {
    onActionConfigChange({ ...actionConfig, resource_type: v });
  };

  const handleTemplateIdChange = (v: number | undefined) => {
    onActionConfigChange({ ...actionConfig, template_id: v });
  };

  const { templates, loading, fallback, error } = useAAPTemplates(integrationId, aapResourceType, debouncedSearch || undefined);

  const options = templates.map((t) => ({ value: t.id, label: t.name }));
  if (aapTemplateId && !templates.find((t) => t.id === aapTemplateId) && templates.length > 0) {
    options.unshift({ value: aapTemplateId, label: `Template #${aapTemplateId} (introuvable)` });
  }

  return (
    <Form.Item label="Quel automatisme appeler ?" style={{ marginBottom: 0 }}>
      <Space wrap>
        <Form.Item label="Type de ressource" style={{ marginBottom: 0 }}>
          <Select
            value={aapResourceType}
            onChange={handleResourceTypeChange}
            options={[
              { value: 'job_template', label: 'Job template' },
              { value: 'workflow_job', label: 'Workflow job' },
            ]}
            style={{ width: 160 }}
            aria-label="Type ressource AAP"
            disabled={isReadOnly}
          />
        </Form.Item>
        {fallback ? (
          <>
            {(error || !integrationId) && (
              <Alert
                type="warning"
                showIcon
                title="Saisie manuelle — liste non disponible"
                style={{ marginBottom: 8 }}
              />
            )}
            <Form.Item
              label="ID template (manuel)"
              required
              validateStatus={aapTemplateId == null || aapTemplateId < 1 ? 'error' : ''}
              help={aapTemplateId == null || aapTemplateId < 1 ? 'ID du job template ou workflow job template AAP' : ''}
              style={{ marginBottom: 0 }}
            >
              <Input
                type="number"
                min={1}
                value={aapTemplateId ?? ''}
                onChange={(e) => handleTemplateIdChange(e.target.value ? Number(e.target.value) : undefined)}
                placeholder="ID template AAP"
                style={{ width: 120 }}
                aria-label="ID template AAP"
                disabled={isReadOnly}
              />
            </Form.Item>
          </>
        ) : (
          <Form.Item
            label="Template AAP"
            required
            validateStatus={aapTemplateId == null || aapTemplateId < 1 ? 'error' : ''}
            help={aapTemplateId == null || aapTemplateId < 1 ? 'Selectionnez un template AAP' : ''}
            style={{ marginBottom: 0 }}
          >
            <Select
              showSearch
              loading={loading}
              style={{ minWidth: 240 }}
              value={aapTemplateId ?? undefined}
              onChange={(val) => handleTemplateIdChange(val)}
              onSearch={setSearchInput}
              placeholder="Selectionnez un template"
              filterOption={(input, opt) =>
                ((opt?.label as string) ?? '').toLowerCase().includes(input.toLowerCase())
              }
              options={options}
              aria-label="Template AAP"
              notFoundContent={loading ? 'Chargement...' : 'Aucun template'}
              disabled={isReadOnly}
            />
          </Form.Item>
        )}
      </Space>
    </Form.Item>
  );
}

// ─── WizardStep2Automatisme ────────────────────────────────────────────────────

export interface WizardStep2AutomatismeProps {
  isWorkflow: boolean;
  isReadOnly: boolean;
  /** Story 83-8: remplace connectorType + aapResourceType/aapTemplateId — capabilities complètes. */
  platformCap: PlatformCapability | null;
  /** ID de l'intégration sélectionnée — nécessaire pour WizardAAPTemplateSection (recherche templates). */
  integrationId?: number;
  /** Story 83-8: état unifié de configuration de plateforme (remplace aapResourceType+aapTemplateId). */
  actionConfig: Record<string, unknown>;
  setActionConfig: (v: Record<string, unknown>) => void;
  parameterList: ParameterDefinition[];
  setParameterList: (list: ParameterDefinition[]) => void;
  workflowSteps: WorkflowStep[];
  setWorkflowSteps: (steps: WorkflowStep[]) => void;
  workflowViewMode: 'list' | 'visual';
  setWorkflowViewMode: (mode: 'list' | 'visual') => void;
  /** Story 63.3: ID du workflow pour le VariablePicker. */
  workflowId?: number;
}

function hasPlatformConfigSchema(platformCap: PlatformCapability | null): boolean {
  if (!platformCap?.action_config_schema) return false;
  const schema = platformCap.action_config_schema as Record<string, unknown>;
  if (Object.keys(schema).length === 0) return false;
  // Exige au moins une propriété déclarée pour que SchemaFormRenderer ait quelque chose à rendre.
  const properties = (schema.properties as object) ?? {};
  return Object.keys(properties).length > 0;
}

export function WizardStep2Automatisme({
  isWorkflow,
  isReadOnly,
  platformCap,
  integrationId,
  actionConfig,
  setActionConfig,
  parameterList,
  setParameterList,
  workflowSteps,
  setWorkflowSteps,
  workflowViewMode,
  setWorkflowViewMode,
  workflowId,
}: WizardStep2AutomatismeProps) {

  const hasSchema = hasPlatformConfigSchema(platformCap);
  // Cas exceptionnel connecteur aap : WizardAAPTemplateSection nécessite un composant UI
  // dédié pour lister et sélectionner les templates depuis l'API AAP — non déclaratisable (Story 83-14)
  const isAAP = platformCap?.connector_type === 'aap';

  return (
    <Space orientation="vertical" style={{ width: '100%' }} size="middle">
      {isWorkflow ? (
        <Form.Item
          label="Étapes du workflow"
          tooltip="Définissez les actions qui composent ce workflow, dans l'ordre d'exécution."
        >
          <Space orientation="vertical" style={{ width: '100%' }}>
            {/* Story 20.6 Task 4.4: Contextual help message for workflows */}
            <Alert
              type="info"
              showIcon
              title="Un workflow enchaîne des actions existantes dans l'ordre défini. Aucun connecteur à configurer : chaque étape utilise le connecteur de l'action référencée."
              style={{ marginBottom: 8 }}
            />
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
                workflowId={workflowId}
              />
            )}
          </Space>
        </Form.Item>
      ) : (
        <>
          {/* Story 83-8: Rendu déclaratif — règle de choix du renderer */}
          {hasSchema && isAAP && (
            <WizardAAPTemplateSection
              integrationId={integrationId}
              actionConfig={actionConfig}
              onActionConfigChange={setActionConfig}
              isReadOnly={isReadOnly}
            />
          )}

          {hasSchema && !isAAP && (
            <SchemaFormRenderer
              schema={platformCap!.action_config_schema as Record<string, unknown>}
              value={actionConfig}
              onChange={setActionConfig}
              disabled={isReadOnly}
            />
          )}
          <Form.Item
            label="Paramètres"
            tooltip="Définissez les paramètres de l'action (extra_vars, etc.)."
          >
            <ParametersEditor value={parameterList} onChange={setParameterList} disabled={isReadOnly} />
          </Form.Item>
        </>
      )}
    </Space>
  );
}

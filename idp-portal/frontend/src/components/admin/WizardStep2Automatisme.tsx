/**
 * WizardStep2Automatisme — Étape 2 du wizard (Automatisme & Paramètres) extraite de ActionWizard (Story 33.5, Task 5).
 * Contient : WorkflowStepsEditor ou (SchemaFormRenderer + ParametersEditor) selon le type.
 *
 * Story 84-6: Exception AAP réduite au strict minimum.
 *   - Couche rendu : un seul bloc SchemaFormRenderer pour tous les connecteurs y compris AAP.
 *   - resource_type (enum) → rendu standard automatique par SchemaFormRenderer.
 *   - template_id (source externe API AAP) → AAPTemplateIdRenderer via customRenderers.
 *   - isAAP utilisé uniquement pour définir aapCustomRenderers — plus de branchement JSX.
 *   - Couche payload : buildConnectorConfig() dans ActionWizard conservé sans modification
 *     (frontière incompressible frontend/backend — cf. commentaire Story 83-14).
 */
import { useState, useMemo } from 'react';
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

// ─── AAPTemplateIdRenderer (renderer local, non exporté) ──────────────────────
// Encapsule la logique de sélection du template AAP (source externe : API AAP via useAAPTemplates).
// Le label et la description sont gérés par SchemaFormRenderer (wrapper Form.Item) — ce composant
// ne fournit que le widget input (même principe que Story 84-5 pour gateCustomRenderers).

interface AAPTemplateIdRendererProps {
  integrationId: number | undefined;
  resourceType: 'job_template' | 'workflow_job';
  value: number | undefined;
  onChange: (v: unknown) => void;
  disabled: boolean;
}

function AAPTemplateIdRenderer({
  integrationId,
  resourceType,
  value,
  onChange,
  disabled,
}: AAPTemplateIdRendererProps) {
  const [searchInput, setSearchInput] = useState('');
  const debouncedSearch = useDebounce(searchInput, 300);

  const { templates, loading, fallback, error } = useAAPTemplates(
    integrationId,
    resourceType,
    debouncedSearch || undefined,
  );

  const options = templates.map((t) => ({ value: t.id, label: t.name }));
  if (value && !templates.find((t) => t.id === value) && templates.length > 0) {
    options.unshift({ value, label: `Template #${value} (introuvable)` });
  }

  if (fallback) {
    return (
      <>
        {(error || !integrationId) && (
          <Alert
            type="warning"
            showIcon
            title="Saisie manuelle — liste non disponible"
            style={{ marginBottom: 8 }}
          />
        )}
        <Input
          type="number"
          min={1}
          value={value ?? ''}
          onChange={(e) => onChange(e.target.value ? Number(e.target.value) : undefined)}
          placeholder="ID template AAP"
          style={{ width: 120 }}
          aria-label="ID template AAP"
          disabled={disabled}
        />
      </>
    );
  }

  return (
    <Select
      showSearch
      loading={loading}
      style={{ minWidth: 240 }}
      value={value ?? undefined}
      onChange={(val) => onChange(val)}
      onSearch={setSearchInput}
      placeholder="Sélectionnez un template"
      filterOption={(input, opt) =>
        ((opt?.label as string) ?? '').toLowerCase().includes(input.toLowerCase())
      }
      options={options}
      aria-label="Template AAP"
      notFoundContent={loading ? 'Chargement...' : 'Aucun template'}
      disabled={disabled}
    />
  );
}

// ─── WizardStep2Automatisme ────────────────────────────────────────────────────

export interface WizardStep2AutomatismeProps {
  isWorkflow: boolean;
  isReadOnly: boolean;
  /** Story 83-8: remplace connectorType + aapResourceType/aapTemplateId — capabilities complètes. */
  platformCap: PlatformCapability | null;
  /** ID de l'intégration sélectionnée — nécessaire pour AAPTemplateIdRenderer (recherche templates). */
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
  // isAAP utilisé uniquement pour définir aapCustomRenderers — pas de branchement JSX (Story 84-6)
  const isAAP = platformCap?.connector_type === 'aap';

  // Story 84-6: custom renderer pour template_id uniquement (source externe : API AAP).
  // resource_type est un enum → rendu standard Select par SchemaFormRenderer (aucun custom renderer).
  // Pattern identique à gateCustomRenderers de Story 84-5 (closure pour accéder à resource_type).
  const aapCustomRenderers = useMemo(() => {
    if (!isAAP) return undefined;
    const resourceType = (actionConfig.resource_type as 'job_template' | 'workflow_job') ?? 'job_template';
    return {
      template_id: (value: unknown, onChange: (v: unknown) => void, disabled: boolean) => (
        <AAPTemplateIdRenderer
          integrationId={integrationId}
          resourceType={resourceType}
          value={value as number | undefined}
          onChange={onChange}
          disabled={disabled}
        />
      ),
    };
  }, [isAAP, integrationId, actionConfig.resource_type]);

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
          {/* Story 84-6: Un seul bloc SchemaFormRenderer gère tous les connecteurs y compris AAP.
              aapCustomRenderers est undefined pour les connecteurs non-AAP → comportement identique. */}
          {hasSchema && (
            <SchemaFormRenderer // B.5 done (story 84-6)
              schema={platformCap!.action_config_schema as Record<string, unknown>}
              value={actionConfig}
              onChange={setActionConfig}
              disabled={isReadOnly}
              customRenderers={aapCustomRenderers}
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

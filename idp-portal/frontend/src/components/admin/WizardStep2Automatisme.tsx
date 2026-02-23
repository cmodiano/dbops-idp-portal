/**
 * WizardStep2Automatisme — Étape 2 du wizard (Automatisme & Paramètres) extraite de ActionWizard (Story 33.5, Task 5).
 * Contient : WorkflowStepsEditor ou (WizardAAPTemplateSection + ParametersEditor) selon le type.
 * Note : WizardAAPTemplateSection est co-localisé ici car utilisé exclusivement dans cette étape.
 */
import { useEffect, useState } from 'react';
import { Form, Input, Select, Alert, Space, Radio } from 'antd';
import type {
  ParameterDefinition,
  WorkflowStep,
} from '../../types/api';
import { ParametersEditor } from './ParametersEditor';
import { WorkflowStepsEditor } from './WorkflowStepsEditor';
import { WorkflowBuilderCanvas } from './WorkflowBuilderCanvas';
import { useAAPTemplates } from '../../hooks/useAAPTemplates';

// ─── WizardAAPTemplateSection (composant local, non exporté) ─────────────────

interface WizardAAPTemplateSectionProps {
  integrationId: number | undefined;
  aapResourceType: 'job_template' | 'workflow_job';
  aapTemplateId: number | undefined;
  onResourceTypeChange: (v: 'job_template' | 'workflow_job') => void;
  onTemplateIdChange: (v: number | undefined) => void;
  isReadOnly: boolean;
}

function WizardAAPTemplateSection({
  integrationId,
  aapResourceType,
  aapTemplateId,
  onResourceTypeChange,
  onTemplateIdChange,
  isReadOnly,
}: WizardAAPTemplateSectionProps) {
  const [searchInput, setSearchInput] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  useEffect(() => {
    const timer = setTimeout(() => setDebouncedSearch(searchInput), 300);
    return () => clearTimeout(timer);
  }, [searchInput]);

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
            onChange={onResourceTypeChange}
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
                onChange={(e) => onTemplateIdChange(e.target.value ? Number(e.target.value) : undefined)}
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
              onChange={(val) => onTemplateIdChange(val)}
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
  isPlatformAAP: boolean;
  integrationId: number | undefined;
  aapResourceType: 'job_template' | 'workflow_job';
  setAapResourceType: (v: 'job_template' | 'workflow_job') => void;
  aapTemplateId: number | undefined;
  setAapTemplateId: (v: number | undefined) => void;
  parameterList: ParameterDefinition[];
  setParameterList: (list: ParameterDefinition[]) => void;
  workflowSteps: WorkflowStep[];
  setWorkflowSteps: (steps: WorkflowStep[]) => void;
  workflowViewMode: 'list' | 'visual';
  setWorkflowViewMode: (mode: 'list' | 'visual') => void;
}

export function WizardStep2Automatisme({
  isWorkflow,
  isReadOnly,
  isPlatformAAP,
  integrationId,
  aapResourceType,
  setAapResourceType,
  aapTemplateId,
  setAapTemplateId,
  parameterList,
  setParameterList,
  workflowSteps,
  setWorkflowSteps,
  workflowViewMode,
  setWorkflowViewMode,
}: WizardStep2AutomatismeProps) {
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
              message="Un workflow enchaîne des actions existantes dans l'ordre défini. Aucun connecteur à configurer : chaque étape utilise le connecteur de l'action référencée."
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
              />
            )}
          </Space>
        </Form.Item>
      ) : (
        <>
          {isPlatformAAP && (
            <WizardAAPTemplateSection
              integrationId={integrationId}
              aapResourceType={aapResourceType}
              aapTemplateId={aapTemplateId}
              onResourceTypeChange={setAapResourceType}
              onTemplateIdChange={setAapTemplateId}
              isReadOnly={isReadOnly}
            />
          )}
          <Form.Item
            label="Paramètres"
            tooltip="Définissez les paramètres de l'action (extra_vars, etc.)."
          >
            {/* TODO: Add disabled prop to ParametersEditor */}
            <ParametersEditor value={parameterList} onChange={isReadOnly ? () => {} : setParameterList} />
          </Form.Item>
        </>
      )}
    </Space>
  );
}

/**
 * StepsEditor component for managing execution steps (Story 2.2, AC #1, #2).
 *
 * Features:
 * - Ordered list of steps with drag-and-drop reordering via @dnd-kit
 * - Step name, type, ServiceNow change flag, conditional environments
 * - Inline validation
 * - Accessibility support
 */

import { useState, useMemo } from 'react';
import type { FC, CSSProperties } from 'react';
import {
  Alert,
  Button,
  Input,
  Select,
  Space,
  Card,
  Typography,
  Form,
  theme,
} from 'antd';
import { PlusOutlined, DeleteOutlined, HolderOutlined } from '@ant-design/icons';
import {
  DndContext,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  type DragEndEvent,
} from '@dnd-kit/core';
import {
  arrayMove,
  SortableContext,
  sortableKeyboardCoordinates,
  useSortable,
  verticalListSortingStrategy,
} from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import type { ExecutionStep, ExecutionStepType, ConnectorType } from '../../types/api';
import { useEnvironments } from '../../hooks/useEnvironments';
import { useAAPTemplates } from '../../hooks/useAAPTemplates';
import { useDebounce } from '../../hooks/useDebounce';
import { useCapabilities } from '../../hooks/useCapabilities';

const { Text } = Typography;

const EMPTY_STEPS: ExecutionStep[] = [];

interface StepsEditorProps {
  value?: ExecutionStep[];
  onChange?: (steps: ExecutionStep[]) => void;
  /** Story 31.5: Integration ID for loading AAP templates. */
  integrationId?: number | null;
}

const STEP_TYPE_OPTIONS: { value: ExecutionStepType; label: string }[] = [
  { value: 'prerequisite', label: 'Pre-requis' },
  { value: 'execution', label: 'Execution' },
  { value: 'verification', label: 'Verification' },
];

/** Connector options for execution steps (Story 2.7). Aligned with backend. */
const CONNECTOR_OPTIONS: { value: ConnectorType; label: string }[] = [
  { value: 'none', label: 'Aucun' },
  { value: 'servicenow', label: 'ServiceNow' },
  { value: 'aap', label: 'AAP' },
  { value: 'azuredevops', label: 'Azure DevOps' },
  { value: 'jira', label: 'Jira' },
  { value: 'github_actions', label: 'GitHub Actions' },
  { value: 'terraform', label: 'Terraform' },
];

/** Props for the sortable step card */
interface SortableStepCardProps {
  step: ExecutionStep;
  index: number;
  environmentOptions: { value: string; label: string }[];
  environmentsLoading: boolean;
  connectorOptions: { value: ConnectorType; label: string }[];
  onStepChange: (index: number, field: keyof ExecutionStep, fieldValue: unknown) => void;
  onRemoveStep: (index: number) => void;
  /** When false, remove button is disabled (at least one step required). */
  canRemove: boolean;
  /** Story 31.5: Integration ID for AAP template loading. */
  integrationId?: number | null;
}

/** Story 31.5: AAP template selector — separate component to use hooks safely. */
interface AAPTemplateSectionProps {
  step: ExecutionStep;
  index: number;
  integrationId?: number | null;
  onStepChange: (index: number, field: keyof ExecutionStep, fieldValue: unknown) => void;
}

const AAPTemplateSection: FC<AAPTemplateSectionProps> = ({
  step,
  index,
  integrationId,
  onStepChange,
}) => {
  const resourceType = ((step.connector_config?.resource_type as string) ?? 'job_template') as 'job_template' | 'workflow_job';
  const connectorCfg = step.connector_config as Record<string, unknown> | null;
  const currentId = resourceType === 'workflow_job'
    ? (connectorCfg?.['workflow_job_template_id'] as number | undefined)
    : (connectorCfg?.['job_template_id'] as number | undefined);

  // H3 fix: debounced search for server-side filtering (AC3)
  const [searchInput, setSearchInput] = useState('');
  const debouncedSearch = useDebounce(searchInput, 300);

  const { templates, loading, fallback, error } = useAAPTemplates(integrationId, resourceType, debouncedSearch || undefined);

  const handleTemplateSelect = (templateId: number) => {
    const cfg: Record<string, unknown> = { ...(step.connector_config || {}), resource_type: resourceType };
    if (resourceType === 'workflow_job') {
      cfg['workflow_job_template_id'] = templateId;
      delete cfg['job_template_id'];
    } else {
      cfg['job_template_id'] = templateId;
      delete cfg['workflow_job_template_id'];
    }
    onStepChange(index, 'connector_config', cfg);
  };

  // Build options with retrocompatibility: if current ID not in list, show warning option
  const options = templates.map((t) => ({ value: t.id, label: t.name }));
  if (currentId && !templates.find((t) => t.id === currentId) && templates.length > 0) {
    options.unshift({ value: currentId, label: `Template #${currentId} (introuvable)` });
  }

  return (
    <>
      <Form.Item label="Type de ressource" style={{ marginBottom: 0 }}>
        <Select
          value={resourceType}
          onChange={(val) =>
            onStepChange(index, 'connector_config', {
              ...(step.connector_config || {}),
              resource_type: val,
            })
          }
          options={[
            { value: 'job_template', label: 'Job template' },
            { value: 'workflow_job', label: 'Workflow job' },
          ]}
          style={{ width: 160 }}
          aria-label={`Type ressource AAP etape ${step.order}`}
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
            validateStatus={currentId == null || currentId === 0 ? 'error' : ''}
            help={currentId == null || currentId === 0 ? 'ID template requis pour une etape AAP' : ''}
            style={{ marginBottom: 0 }}
          >
            <Input
              type="number"
              min={1}
              value={currentId ?? ''}
              onChange={(e) => handleTemplateSelect(e.target.value ? Number(e.target.value) : 0)}
              placeholder="ID du template AAP"
              style={{ width: 120 }}
              aria-label={`ID template AAP etape ${step.order}`}
            />
          </Form.Item>
        </>
      ) : (
        <Form.Item
          label="Template AAP"
          validateStatus={currentId == null ? 'error' : ''}
          help={currentId == null ? 'Selectionnez un template AAP' : ''}
          style={{ marginBottom: 0 }}
        >
          <Select
            showSearch
            loading={loading}
            style={{ minWidth: 240 }}
            value={currentId ?? undefined}
            onChange={handleTemplateSelect}
            onSearch={setSearchInput}
            placeholder="Selectionnez un template"
            filterOption={(input, opt) =>
              ((opt?.label as string) ?? '').toLowerCase().includes(input.toLowerCase())
            }
            options={options}
            aria-label={`Template AAP etape ${step.order}`}
            notFoundContent={loading ? 'Chargement...' : 'Aucun template'}
          />
        </Form.Item>
      )}
    </>
  );
};

/** Sortable step card component using @dnd-kit */
const SortableStepCard: FC<SortableStepCardProps> = ({
  step,
  index,
  environmentOptions,
  environmentsLoading,
  connectorOptions,
  onStepChange,
  onRemoveStep,
  canRemove,
  integrationId,
}) => {
  const { token } = theme.useToken();
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id: step.order.toString() });

  const style: CSSProperties = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1,
    marginBottom: 8,
  };

  return (
    <Card
      ref={setNodeRef}
      style={style}
      size="small"
      styles={{
        body: { padding: '12px' },
      }}
    >
      <Space orientation="vertical" style={{ width: '100%' }}>
        <Space align="center" style={{ width: '100%', justifyContent: 'space-between' }}>
          <Space>
            <HolderOutlined
              {...attributes}
              {...listeners}
              style={{ cursor: isDragging ? 'grabbing' : 'grab', color: token.colorTextTertiary, touchAction: 'none' }}
              aria-label={`Glisser pour reordonner etape ${step.order}`}
            />
            <Text strong>Etape {step.order}</Text>
          </Space>
          <Button
            size="small"
            danger
            icon={<DeleteOutlined />}
            onClick={() => onRemoveStep(index)}
            disabled={!canRemove}
            aria-label={canRemove ? `Supprimer etape ${step.order}` : 'Au moins une etape requise'}
          />
        </Space>

        <Space wrap style={{ width: '100%' }}>
          <Form.Item
            label="Nom"
            validateStatus={!step.name ? 'error' : ''}
            help={!step.name ? 'Nom requis' : ''}
            style={{ marginBottom: 0 }}
          >
            <Input
              value={step.name}
              onChange={(e) => onStepChange(index, 'name', e.target.value)}
              placeholder="Nom de l'etape"
              style={{ width: 200 }}
              aria-label={`Nom etape ${step.order}`}
            />
          </Form.Item>

          <Form.Item label="Type" style={{ marginBottom: 0 }}>
            <Select
              value={step.type}
              onChange={(val) => onStepChange(index, 'type', val)}
              options={STEP_TYPE_OPTIONS}
              style={{ width: 140 }}
              aria-label={`Type etape ${step.order}`}
            />
          </Form.Item>

          <Form.Item label="Connecteur" style={{ marginBottom: 0 }}>
            <Select
              value={step.connector_type ?? 'none'}
              onChange={(val) => onStepChange(index, 'connector_type', val)}
              options={connectorOptions}
              style={{ width: 160 }}
              aria-label={`Connecteur etape ${step.order}`}
            />
          </Form.Item>

          {step.connector_type === 'servicenow' && (
            <Form.Item
              label="Environnements"
              validateStatus={
                step.connector_type === 'servicenow' &&
                (!step.conditional_environments || step.conditional_environments.length === 0)
                  ? 'error'
                  : ''
              }
              help={
                step.connector_type === 'servicenow' &&
                (!step.conditional_environments || step.conditional_environments.length === 0)
                  ? 'Selectionnez au moins un environnement'
                  : ''
              }
              style={{ marginBottom: 0 }}
            >
              <Select
                mode="multiple"
                value={step.conditional_environments || []}
                onChange={(val) => onStepChange(index, 'conditional_environments', val)}
                placeholder="Environnements conditionnes"
                style={{ minWidth: 180 }}
                options={environmentOptions}
                loading={environmentsLoading}
                disabled={environmentsLoading}
                aria-label={`Environnements conditionnes etape ${step.order}`}
              />
            </Form.Item>
          )}

          {/* Story 31.5: AAP template selector (list or manual fallback) */}
          {step.connector_type === 'aap' && (
            <AAPTemplateSection
              step={step}
              index={index}
              integrationId={integrationId}
              onStepChange={onStepChange}
            />
          )}
        </Space>
      </Space>
    </Card>
  );
};

export const StepsEditor: FC<StepsEditorProps> = ({ value = EMPTY_STEPS, onChange, integrationId }) => {
  const { environmentOptions, loading: environmentsLoading } = useEnvironments();
  const { capabilities } = useCapabilities();

  // Story 82.8: connecteurs depuis capabilities.platforms (dédupliqués par connector_type)
  const connectorOptions = useMemo<{ value: ConnectorType; label: string }[]>(() => {
    const noneOption = { value: 'none' as ConnectorType, label: 'Aucun' };
    if (!capabilities?.platforms?.length) return CONNECTOR_OPTIONS;
    const seen = new Set<string>();
    const platformOpts = capabilities.platforms
      .filter((p) => {
        if (seen.has(p.connector_type)) return false;
        seen.add(p.connector_type);
        return true;
      })
      .map((p) => ({ value: p.connector_type as ConnectorType, label: p.display_name }));
    return [noneOption, ...platformOpts];
  }, [capabilities]);

  // Configure dnd-kit sensors for pointer and keyboard interaction
  const sensors = useSensors(
    useSensor(PointerSensor),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    })
  );

  const handleAddStep = () => {
    const newStep: ExecutionStep = {
      order: value.length + 1,
      name: '',
      type: 'execution',
      connector_type: 'none',
      connector_config: null,
      conditional_environments: null,
    };
    onChange?.([...value, newStep]);
  };

  const handleRemoveStep = (index: number) => {
    const newSteps = value.filter((_, i) => i !== index).map((step, i) => ({
      ...step,
      order: i + 1,
    }));
    onChange?.(newSteps);
  };

  const handleStepChange = (index: number, field: keyof ExecutionStep, fieldValue: unknown) => {
    const newSteps = [...value];
    newSteps[index] = { ...newSteps[index], [field]: fieldValue };

    // If connector is no longer servicenow, clear conditional_environments (Story 2.7)
    if (field === 'connector_type' && fieldValue !== 'servicenow') {
      newSteps[index].conditional_environments = null;
    }

    onChange?.(newSteps);
  };

  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event;

    if (over && active.id !== over.id) {
      const oldIndex = value.findIndex((step) => step.order.toString() === active.id);
      const newIndex = value.findIndex((step) => step.order.toString() === over.id);

      const reorderedSteps = arrayMove(value, oldIndex, newIndex).map((step, i) => ({
        ...step,
        order: i + 1,
      }));

      onChange?.(reorderedSteps);
    }
  };

  // Generate sortable IDs from step order
  const sortableIds = value.map((step) => step.order.toString());

  return (
    <div>
      <Space orientation="vertical" style={{ width: '100%' }}>
        <DndContext
          sensors={sensors}
          collisionDetection={closestCenter}
          onDragEnd={handleDragEnd}
        >
          <SortableContext items={sortableIds} strategy={verticalListSortingStrategy}>
            {value.map((step, index) => (
              <SortableStepCard
                key={step.order}
                step={step}
                index={index}
                environmentOptions={environmentOptions}
                environmentsLoading={environmentsLoading}
                connectorOptions={connectorOptions}
                onStepChange={handleStepChange}
                onRemoveStep={handleRemoveStep}
                canRemove={value.length > 1}
                integrationId={integrationId}
              />
            ))}
          </SortableContext>
        </DndContext>

        {value.length === 0 && (
          <Text type="secondary">Aucune etape definie. Ajoutez au moins une etape.</Text>
        )}

        <Button type="dashed" onClick={handleAddStep} icon={<PlusOutlined />} block>
          Ajouter une etape
        </Button>
      </Space>
    </div>
  );
};

export default StepsEditor;

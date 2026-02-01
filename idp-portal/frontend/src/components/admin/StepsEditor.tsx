/**
 * StepsEditor component for managing execution steps (Story 2.2, AC #1, #2).
 *
 * Features:
 * - Ordered list of steps with drag-and-drop reordering via @dnd-kit
 * - Step name, type, ServiceNow change flag, conditional environments
 * - Inline validation
 * - Accessibility support
 */

import React from 'react';
import {
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

const { Text } = Typography;

interface StepsEditorProps {
  value?: ExecutionStep[];
  onChange?: (steps: ExecutionStep[]) => void;
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

const ENVIRONMENT_OPTIONS = ['DEV', 'STAGING', 'PROD'];

/** Props for the sortable step card */
interface SortableStepCardProps {
  step: ExecutionStep;
  index: number;
  onStepChange: (index: number, field: keyof ExecutionStep, fieldValue: unknown) => void;
  onRemoveStep: (index: number) => void;
  /** When false, remove button is disabled (at least one step required). */
  canRemove: boolean;
}

/** Sortable step card component using @dnd-kit */
const SortableStepCard: React.FC<SortableStepCardProps> = ({
  step,
  index,
  onStepChange,
  onRemoveStep,
  canRemove,
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

  const style: React.CSSProperties = {
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
              options={CONNECTOR_OPTIONS}
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
                options={ENVIRONMENT_OPTIONS.map((env) => ({ value: env, label: env }))}
                aria-label={`Environnements conditionnes etape ${step.order}`}
              />
            </Form.Item>
          )}

          {/* Story 4.10 AC4: Type de ressource AAP (job template | workflow job) */}
          {step.connector_type === 'aap' && (
            <>
              <Form.Item label="Type de ressource" style={{ marginBottom: 0 }}>
                <Select
                  value={(step.connector_config?.resource_type as string) ?? 'job_template'}
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
              <Form.Item
                label="ID template"
                validateStatus={
                  step.connector_type === 'aap' &&
                  (step.connector_config?.resource_type === 'workflow_job'
                    ? (step.connector_config?.workflow_job_template_id == null ||
                        step.connector_config?.workflow_job_template_id === '' ||
                        step.connector_config?.workflow_job_template_id === 0)
                    : (step.connector_config?.job_template_id == null ||
                        step.connector_config?.job_template_id === '' ||
                        step.connector_config?.job_template_id === 0))
                    ? 'error'
                    : ''
                }
                help={
                  step.connector_type === 'aap' &&
                  (step.connector_config?.resource_type === 'workflow_job'
                    ? (step.connector_config?.workflow_job_template_id == null ||
                        step.connector_config?.workflow_job_template_id === '' ||
                        step.connector_config?.workflow_job_template_id === 0)
                    : (step.connector_config?.job_template_id == null ||
                        step.connector_config?.job_template_id === '' ||
                        step.connector_config?.job_template_id === 0))
                    ? 'ID template requis pour une etape AAP'
                    : ''
                }
                style={{ marginBottom: 0 }}
              >
                <Input
                  type="number"
                  min={1}
                  value={
                    (step.connector_config?.resource_type === 'workflow_job'
                      ? step.connector_config?.workflow_job_template_id
                      : step.connector_config?.job_template_id) ?? ''
                  }
                  onChange={(e) => {
                    const v = e.target.value ? Number(e.target.value) : undefined;
                    const cfg = { ...(step.connector_config || {}), resource_type: step.connector_config?.resource_type ?? 'job_template' };
                    if (cfg.resource_type === 'workflow_job') {
                      cfg.workflow_job_template_id = v;
                      delete cfg.job_template_id;
                    } else {
                      cfg.job_template_id = v;
                      delete cfg.workflow_job_template_id;
                    }
                    onStepChange(index, 'connector_config', cfg);
                  }}
                  placeholder="ID du template AAP"
                  style={{ width: 120 }}
                  aria-label={`ID template AAP etape ${step.order}`}
                />
              </Form.Item>
            </>
          )}
        </Space>
      </Space>
    </Card>
  );
};

export const StepsEditor: React.FC<StepsEditorProps> = ({ value = [], onChange }) => {
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
                onStepChange={handleStepChange}
                onRemoveStep={handleRemoveStep}
                canRemove={value.length > 1}
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

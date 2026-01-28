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
  Switch,
  Space,
  Card,
  Typography,
  Form,
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
import type { ExecutionStep, ExecutionStepType } from '../../types/api';

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
      <Space direction="vertical" style={{ width: '100%' }}>
        <Space align="center" style={{ width: '100%', justifyContent: 'space-between' }}>
          <Space>
            <HolderOutlined
              {...attributes}
              {...listeners}
              style={{ cursor: isDragging ? 'grabbing' : 'grab', color: '#999', touchAction: 'none' }}
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

          <Form.Item label="Changement ServiceNow" style={{ marginBottom: 0 }}>
            <Switch
              checked={step.is_servicenow_change}
              onChange={(checked) => onStepChange(index, 'is_servicenow_change', checked)}
              aria-label={`Changement ServiceNow etape ${step.order}`}
            />
          </Form.Item>

          {step.is_servicenow_change && (
            <Form.Item
              label="Environnements"
              validateStatus={
                step.is_servicenow_change &&
                (!step.conditional_environments || step.conditional_environments.length === 0)
                  ? 'error'
                  : ''
              }
              help={
                step.is_servicenow_change &&
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
      is_servicenow_change: false,
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

    // If ServiceNow is unchecked, clear conditional_environments
    if (field === 'is_servicenow_change' && !fieldValue) {
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
      <Space direction="vertical" style={{ width: '100%' }}>
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

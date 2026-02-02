/**
 * WorkflowStepsEditor — Éditeur d'étapes pour workflows (Story 9.5, AC2, AC4).
 *
 * Features:
 * - Ordered list of workflow steps with drag-and-drop reordering via @dnd-kit
 * - AutoComplete for selecting existing published actions
 * - Optional display name per step
 * - Inline validation (at least 1 step required, each step must have referenced_action_id)
 * - Accessibility support (WCAG 2.1 AA)
 */

import React, { useState, useEffect, useMemo } from 'react';
import {
  Button,
  Input,
  AutoComplete,
  Space,
  Card,
  Typography,
  Alert,
  Spin,
  Tooltip,
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
import type { WorkflowStep, ActionListItem } from '../../types/api';
import { getEligibleActionsForWorkflow } from '../../services/admin_service';

const { Text } = Typography;

/** Extended step type with optional temporary id for new steps. */
interface WorkflowStepEditable extends Omit<WorkflowStep, 'referenced_action_id'> {
  referenced_action_id: number | undefined;
  /** Temporary unique ID for react key and dnd-kit. */
  _tempId?: string;
}

export interface WorkflowStepsEditorProps {
  /** Current workflow steps. */
  steps: WorkflowStep[];
  /** Callback when steps change. */
  onChange: (steps: WorkflowStep[]) => void;
  /** Show loading state. */
  loading?: boolean;
}

interface SortableStepCardProps {
  step: WorkflowStepEditable;
  index: number;
  eligibleActions: ActionListItem[];
  loadingActions: boolean;
  onStepChange: (index: number, field: keyof WorkflowStepEditable, value: unknown) => void;
  onRemoveStep: (index: number) => void;
  canRemove: boolean;
  hasError: boolean;
}

/** Sortable step card using @dnd-kit. */
const SortableStepCard: React.FC<SortableStepCardProps> = ({
  step,
  index,
  eligibleActions,
  loadingActions,
  onStepChange,
  onRemoveStep,
  canRemove,
  hasError,
}) => {
  const { token } = theme.useToken();
  const stepId = step._tempId ?? `step-${step.order}`;
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id: stepId });

  const style: React.CSSProperties = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1,
    marginBottom: 8,
  };

  // Build AutoComplete options from eligible actions
  const actionOptions = useMemo(
    () =>
      eligibleActions.map((a) => ({
        value: String(a.id),
        label: `${a.name}${a.engine ? ` (${a.engine})` : ''}`,
        actionId: a.id,
      })),
    [eligibleActions]
  );

  // Get the selected action for display
  const selectedAction = eligibleActions.find((a) => a.id === step.referenced_action_id);
  const displayValue = selectedAction
    ? `${selectedAction.name}${selectedAction.engine ? ` (${selectedAction.engine})` : ''}`
    : '';

  return (
    <Card
      ref={setNodeRef}
      style={style}
      size="small"
      styles={{
        body: { padding: '12px' },
      }}
    >
      <Space orientation="vertical" style={{ width: '100%' }} size="small">
        <Space align="center" style={{ width: '100%', justifyContent: 'space-between' }}>
          <Space>
            <HolderOutlined
              {...attributes}
              {...listeners}
              style={{
                cursor: isDragging ? 'grabbing' : 'grab',
                color: token.colorTextTertiary,
                touchAction: 'none',
              }}
              aria-label={`Glisser pour réordonner l'étape ${step.order}`}
            />
            <Text strong>Étape {step.order}</Text>
          </Space>
          <Tooltip title={canRemove ? `Supprimer l'étape ${step.order}` : 'Au moins une étape requise'}>
            <Button
              size="small"
              danger
              icon={<DeleteOutlined />}
              onClick={() => onRemoveStep(index)}
              disabled={!canRemove}
              aria-label={canRemove ? `Supprimer l'étape ${step.order}` : 'Au moins une étape requise'}
            />
          </Tooltip>
        </Space>

        <Space wrap style={{ width: '100%' }}>
          <div style={{ marginBottom: 0 }}>
            <Text type="secondary" style={{ fontSize: 12 }}>
              Action *
            </Text>
            <Tooltip title="Sélectionnez une action publiée existante">
              <AutoComplete
                style={{ width: 280, marginTop: 4, display: 'block' }}
                value={displayValue}
                options={actionOptions}
                placeholder="Rechercher une action..."
                filterOption={(inputValue, option) =>
                  option?.label?.toString().toLowerCase().includes(inputValue.toLowerCase()) ?? false
                }
                onSelect={(value: string) => {
                  const selected = actionOptions.find(opt => opt.value === value);
                  if (selected?.actionId) {
                    onStepChange(index, 'referenced_action_id', selected.actionId);
                  }
                }}
                onClear={() => onStepChange(index, 'referenced_action_id', undefined)}
                allowClear
                loading={loadingActions}
                status={hasError && !step.referenced_action_id ? 'error' : undefined}
                aria-label="Sélectionner une action"
                notFoundContent={
                  loadingActions ? (
                    <Spin size="small" />
                  ) : eligibleActions.length === 0 ? (
                    'Aucune action publiée disponible'
                  ) : (
                    'Aucun résultat'
                  )
                }
              />
            </Tooltip>
            {hasError && !step.referenced_action_id && (
              <Text type="danger" style={{ fontSize: 12 }} role="alert">
                Action requise
              </Text>
            )}
          </div>

          <div style={{ marginBottom: 0 }}>
            <Tooltip title="Nom personnalisé optionnel pour cette étape dans le workflow">
              <div>
                <Text type="secondary" style={{ fontSize: 12 }}>
                  Nom d'affichage
                </Text>
                <Input
                  style={{ width: 200, marginTop: 4, display: 'block' }}
                  value={step.name ?? ''}
                  onChange={(e) => onStepChange(index, 'name', e.target.value || null)}
                  placeholder="Optionnel"
                  aria-label={`Nom d'affichage de l'étape ${step.order}`}
                />
              </div>
            </Tooltip>
          </div>
        </Space>
      </Space>
    </Card>
  );
};

export const WorkflowStepsEditor: React.FC<WorkflowStepsEditorProps> = ({
  steps,
  onChange,
  loading = false,
}) => {
  const [eligibleActions, setEligibleActions] = useState<ActionListItem[]>([]);
  const [loadingActions, setLoadingActions] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [showValidation, setShowValidation] = useState(false);

  // Convert WorkflowStep[] to internal editable format with tempIds
  const [internalSteps, setInternalSteps] = useState<WorkflowStepEditable[]>(() =>
    steps.map((s, i) => ({
      ...s,
      _tempId: `step-${i}-${Date.now()}`,
    }))
  );

  // Sync external steps to internal state (for edit mode)
  useEffect(() => {
    if (steps.length > 0 && internalSteps.length === 0) {
      setInternalSteps(
        steps.map((s, i) => ({
          ...s,
          _tempId: `step-${i}-${Date.now()}`,
        }))
      );
    }
  }, [steps, internalSteps.length]);

  // Load eligible actions on mount
  useEffect(() => {
    setLoadingActions(true);
    setLoadError(null);
    getEligibleActionsForWorkflow()
      .then((actions) => {
        setEligibleActions(actions);
      })
      .catch((err) => {
        console.error('Failed to load eligible actions for workflow:', err);
        setLoadError(err instanceof Error ? err.message : 'Impossible de charger les actions éligibles');
        setEligibleActions([]);
      })
      .finally(() => {
        setLoadingActions(false);
      });
  }, []);

  // Notify parent of changes (filter out internal fields)
  const notifyChange = (newSteps: WorkflowStepEditable[]) => {
    setInternalSteps(newSteps);
    onChange(
      newSteps
        .filter((s) => s.referenced_action_id !== undefined && typeof s.referenced_action_id === 'number')
        .map(({ _tempId, ...rest }) => ({
          ...rest,
          referenced_action_id: rest.referenced_action_id!,
        }))
    );
  };

  // Configure dnd-kit sensors
  const sensors = useSensors(
    useSensor(PointerSensor),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    })
  );

  const handleAddStep = () => {
    const newStep: WorkflowStepEditable = {
      order: internalSteps.length + 1,
      name: null,
      referenced_action_id: undefined,
      _tempId: `step-new-${Date.now()}`,
    };
    notifyChange([...internalSteps, newStep]);
  };

  const handleRemoveStep = (index: number) => {
    const newSteps = internalSteps
      .filter((_, i) => i !== index)
      .map((step, i) => ({
        ...step,
        order: i + 1,
      }));
    notifyChange(newSteps);
  };

  const handleStepChange = (
    index: number,
    field: keyof WorkflowStepEditable,
    value: unknown
  ) => {
    const newSteps = [...internalSteps];
    newSteps[index] = { ...newSteps[index], [field]: value };
    notifyChange(newSteps);
  };

  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event;

    if (over && active.id !== over.id) {
      const oldIndex = internalSteps.findIndex((step) => (step._tempId ?? `step-${step.order}`) === active.id);
      const newIndex = internalSteps.findIndex((step) => (step._tempId ?? `step-${step.order}`) === over.id);

      if (oldIndex !== -1 && newIndex !== -1) {
        const reorderedSteps = arrayMove(internalSteps, oldIndex, newIndex).map((step, i) => ({
          ...step,
          order: i + 1,
        }));
        notifyChange(reorderedSteps);
      }
    }
  };

  // Expose validation state
  useEffect(() => {
    if (internalSteps.length > 0) {
      const hasIncompleteStep = internalSteps.some((s) => s.referenced_action_id === undefined);
      setShowValidation(hasIncompleteStep);
    } else {
      setShowValidation(false);
    }
  }, [internalSteps]);

  const sortableIds = internalSteps.map((step) => step._tempId ?? `step-${step.order}`);

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: 24 }}>
        <Spin size="large" />
      </div>
    );
  }

  return (
    <div>
      <Space orientation="vertical" style={{ width: '100%' }}>
        {loadError && (
          <Alert
            title="Erreur"
            description={loadError}
            type="error"
            showIcon
            role="alert"
          />
        )}

        {!loadError && eligibleActions.length === 0 && !loadingActions && (
          <Alert
            title="Aucune action publiée disponible"
            description="Créez et publiez des actions d'abord avant de créer un workflow."
            type="info"
            showIcon
          />
        )}

        {internalSteps.length === 0 && (
          <Alert
            title="Au moins une étape est requise"
            description="Ajoutez au moins une étape au workflow."
            type="warning"
            showIcon
            role="alert"
          />
        )}

        <DndContext
          sensors={sensors}
          collisionDetection={closestCenter}
          onDragEnd={handleDragEnd}
        >
          <SortableContext items={sortableIds} strategy={verticalListSortingStrategy}>
            {internalSteps.map((step, index) => (
              <SortableStepCard
                key={step._tempId ?? `step-${step.order}`}
                step={step}
                index={index}
                eligibleActions={eligibleActions}
                loadingActions={loadingActions}
                onStepChange={handleStepChange}
                onRemoveStep={handleRemoveStep}
                canRemove={internalSteps.length > 1}
                hasError={showValidation}
              />
            ))}
          </SortableContext>
        </DndContext>

        <Button
          type="dashed"
          onClick={handleAddStep}
          icon={<PlusOutlined />}
          block
          disabled={loadError !== null || (eligibleActions.length === 0 && !loadingActions)}
          aria-label="Ajouter une étape"
        >
          Ajouter une étape
        </Button>
      </Space>
    </div>
  );
};

export default WorkflowStepsEditor;

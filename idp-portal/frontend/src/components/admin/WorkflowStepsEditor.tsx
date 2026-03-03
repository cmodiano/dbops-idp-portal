/**
 * WorkflowStepsEditor — Éditeur d'étapes pour workflows (Story 9.5, AC2, AC4).
 *
 * Features:
 * - Ordered list of workflow steps with drag-and-drop reordering via @dnd-kit
 * - AutoComplete for selecting existing published actions
 * - Optional display name per step
 * - Inline validation (at least 1 step required, each step must have referenced_action_id)
 * - Accessibility support (WCAG 2.1 AA)
 *
 * Story 34-9 (SOLID-FE-8): SortableStepCard extracted to ./SortableStepCard.tsx (SRP).
 */

import React, { useState, useEffect, useMemo } from 'react';
import {
  Button,
  Space,
  Alert,
  Spin,
} from 'antd';
import { PlusOutlined } from '@ant-design/icons';
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
  verticalListSortingStrategy,
} from '@dnd-kit/sortable';
import type { WorkflowStep } from '../../types/api';
// DIP: services encapsulés dans useEligibleActions — SOLID-FE-4
import { useEligibleActions } from '../../hooks/useEligibleActions';
import { SortableStepCard } from './SortableStepCard';

/** Extended step type with optional temporary id for new steps. */
export interface WorkflowStepEditable extends Omit<WorkflowStep, 'referenced_action_id'> {
  referenced_action_id?: number | null;
  /** Temporary unique ID for react key and dnd-kit. */
  _tempId?: string;
}

// eslint-disable-next-line react-refresh/only-export-components
export function generateStepId(): string {
  // Prefer browser crypto UUID for stability/uniqueness.
  // Fallback is good enough for local editing; backend also enforces uniqueness.
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID();
  }
  return `step-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

export interface WorkflowStepsEditorProps {
  /** Current workflow steps. */
  steps: WorkflowStep[];
  /** Callback when steps change. */
  onChange: (steps: WorkflowStep[]) => void;
  /** Show loading state. */
  loading?: boolean;
  /** Disable editing (read-only mode). */
  disabled?: boolean;
}

export const WorkflowStepsEditor: React.FC<WorkflowStepsEditorProps> = ({
  steps,
  onChange,
  loading = false,
  disabled = false,
}) => {
  // DIP: chargement des actions éligibles via useEligibleActions — SOLID-FE-4
  const { eligibleActions, loadingActions, loadError } = useEligibleActions();
  const [showValidation, setShowValidation] = useState(false);

  // Convert WorkflowStep[] to internal editable format with tempIds
  const [internalSteps, setInternalSteps] = useState<WorkflowStepEditable[]>(() =>
    steps.map((s, i) => ({
      ...s,
      _tempId: `step-${i}-${Date.now()}`,
    }))
  );

  const stepIdsFromEditor = useMemo(
    () =>
      internalSteps
        .map((s) => (s.step_id ? String(s.step_id) : ''))
        .filter((sid) => Boolean(sid)),
    [internalSteps]
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

  // Notify parent of changes (filter out internal fields)
  const notifyChange = (newSteps: WorkflowStepEditable[]) => {
    setInternalSteps(newSteps);
    onChange(
      newSteps
        .filter((s) => s.referenced_action_id !== undefined && typeof s.referenced_action_id === 'number')
        .map(({ _tempId: _, ...rest }) => ({
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
    if (disabled) return;
    const newStep: WorkflowStepEditable = {
      order: internalSteps.length + 1,
      name: null,
      referenced_action_id: undefined,
      step_id: generateStepId(),
      on_success_step_id: null,
      on_error_step_id: null,
      retry_enabled: false,
      retry_max_attempts: null,
      retry_interval_seconds: null,
      retry_backoff_multiplier: null,
      _tempId: `step-new-${Date.now()}`,
    };
    notifyChange([...internalSteps, newStep]);
  };

  const handleRemoveStep = (index: number) => {
    if (disabled) return;
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
    if (disabled) return;
    const newSteps = [...internalSteps];

    const current = newSteps[index] ?? {};
    const next: WorkflowStepEditable = { ...current, [field]: value } as WorkflowStepEditable;

    // Story 16.2: if the user touches branch/retry fields, ensure step_id exists.
    const branchOrRetryFields: Array<keyof WorkflowStepEditable> = [
      'on_success_step_id',
      'on_error_step_id',
      'retry_enabled',
      'retry_max_attempts',
      'retry_interval_seconds',
      'retry_backoff_multiplier',
    ];
    if (branchOrRetryFields.includes(field) && !next.step_id) {
      next.step_id = generateStepId();
    }

    // If enabling retry, apply UI defaults consistent with backend defaults.
    if (field === 'retry_enabled' && value === true) {
      if (next.retry_max_attempts == null) next.retry_max_attempts = 3;
      if (next.retry_interval_seconds == null) next.retry_interval_seconds = 60;
      if (next.retry_backoff_multiplier == null) next.retry_backoff_multiplier = 2.0;
    }

    newSteps[index] = next;
    notifyChange(newSteps);
  };

  const handleDragEnd = (event: DragEndEvent) => {
    if (disabled) return;
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
          sensors={disabled ? [] : sensors}
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
                stepIdsFromEditor={stepIdsFromEditor}
                allSteps={internalSteps}
                onStepChange={handleStepChange}
                onRemoveStep={handleRemoveStep}
                canRemove={internalSteps.length > 1}
                hasError={showValidation}
                disabled={disabled}
              />
            ))}
          </SortableContext>
        </DndContext>

        <Button
          type="dashed"
          onClick={handleAddStep}
          icon={<PlusOutlined />}
          block
          disabled={disabled || loadError !== null || (eligibleActions.length === 0 && !loadingActions)}
          aria-label="Ajouter une étape"
        >
          Ajouter une étape
        </Button>
      </Space>
    </div>
  );
};

export default WorkflowStepsEditor;

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
  Select,
  Switch,
  InputNumber,
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
import logger from '../../services/logger';

const { Text } = Typography;

/** Extended step type with optional temporary id for new steps. */
interface WorkflowStepEditable extends Omit<WorkflowStep, 'referenced_action_id'> {
  referenced_action_id: number | undefined;
  /** Temporary unique ID for react key and dnd-kit. */
  _tempId?: string;
}

function generateStepId(): string {
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

interface SortableStepCardProps {
  step: WorkflowStepEditable;
  index: number;
  eligibleActions: ActionListItem[];
  loadingActions: boolean;
  stepIdsFromEditor: string[];
  onStepChange: (index: number, field: keyof WorkflowStepEditable, value: unknown) => void;
  onRemoveStep: (index: number) => void;
  canRemove: boolean;
  hasError: boolean;
  disabled?: boolean;
}

/** Sortable step card using @dnd-kit. */
const SortableStepCard: React.FC<SortableStepCardProps> = ({
  step,
  index,
  eligibleActions,
  loadingActions,
  stepIdsFromEditor,
  onStepChange,
  onRemoveStep,
  canRemove,
  hasError,
  disabled = false,
}) => {
  const { token } = theme.useToken();
  const EXIT_VALUE = '__exit__';
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

  const stepIdValue = step.step_id ?? '';
  const stepIdOptions = (stepIds: string[]) => stepIds.map((sid) => ({ value: sid, label: sid }));

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
              disabled={disabled || !canRemove}
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
                disabled={disabled}
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
                  disabled={disabled}
                />
              </div>
            </Tooltip>
          </div>

          {/* Story 16.2: advanced fields for branches and retry */}
          <div style={{ marginBottom: 0, minWidth: 240 }}>
            <Text type="secondary" style={{ fontSize: 12 }}>
              ID d’étape (step_id)
            </Text>
            <Tooltip title="Identifiant stable requis pour les branches/retry. Doit être unique dans le workflow.">
              <Input
                style={{ width: 240, marginTop: 4, display: 'block' }}
                value={stepIdValue}
                placeholder="(optionnel si workflow linéaire)"
                onChange={(e) => onStepChange(index, 'step_id', e.target.value || null)}
                aria-label={`step_id de l'étape ${step.order}`}
                disabled={disabled}
              />
            </Tooltip>
          </div>
        </Space>

        <Card
          size="small"
          styles={{ body: { padding: '12px' } }}
          style={{ background: token.colorFillAlter }}
        >
          <Space wrap size="middle" align="start">
            <div>
              <Text type="secondary" style={{ fontSize: 12 }}>
                Branche succès
              </Text>
              <Select
                style={{ width: 240, marginTop: 4, display: 'block' }}
                value={(step.on_success_step_id ?? EXIT_VALUE) as string}
                onChange={(v) => onStepChange(index, 'on_success_step_id', v === EXIT_VALUE ? null : v)}
                options={[
                  { value: EXIT_VALUE, label: '(fin du workflow)' },
                  ...stepIdOptions(
                    stepIdsFromEditor.filter((sid) => sid && sid !== step.step_id)
                  ),
                ]}
                placeholder="Sélectionner step_id..."
                aria-label={`on_success_step_id de l'étape ${step.order}`}
                disabled={disabled}
                allowClear={false}
              />
            </div>

            <div>
              <Text type="secondary" style={{ fontSize: 12 }}>
                Branche erreur
              </Text>
              <Select
                style={{ width: 240, marginTop: 4, display: 'block' }}
                value={(step.on_error_step_id ?? EXIT_VALUE) as string}
                onChange={(v) => onStepChange(index, 'on_error_step_id', v === EXIT_VALUE ? null : v)}
                options={[
                  { value: EXIT_VALUE, label: '(fin du workflow)' },
                  ...stepIdOptions(
                    stepIdsFromEditor.filter((sid) => sid && sid !== step.step_id)
                  ),
                ]}
                placeholder="Sélectionner step_id..."
                aria-label={`on_error_step_id de l'étape ${step.order}`}
                disabled={disabled}
                allowClear={false}
              />
            </div>

            <div>
              <Text type="secondary" style={{ fontSize: 12 }}>
                Retry
              </Text>
              <div style={{ marginTop: 8 }}>
                <Switch
                  checked={Boolean(step.retry_enabled)}
                  onChange={(checked) => onStepChange(index, 'retry_enabled', checked)}
                  disabled={disabled}
                  aria-label={`retry_enabled de l'étape ${step.order}`}
                />
              </div>
            </div>

            <div>
              <Text type="secondary" style={{ fontSize: 12 }}>
                Max tentatives
              </Text>
              <InputNumber
                style={{ width: 160, marginTop: 4, display: 'block' }}
                min={1}
                value={step.retry_max_attempts ?? null}
                onChange={(v) => onStepChange(index, 'retry_max_attempts', v ?? null)}
                disabled={disabled || !step.retry_enabled}
                aria-label={`retry_max_attempts de l'étape ${step.order}`}
              />
            </div>

            <div>
              <Text type="secondary" style={{ fontSize: 12 }}>
                Intervalle (s)
              </Text>
              <InputNumber
                style={{ width: 160, marginTop: 4, display: 'block' }}
                min={1}
                value={step.retry_interval_seconds ?? null}
                onChange={(v) => onStepChange(index, 'retry_interval_seconds', v ?? null)}
                disabled={disabled || !step.retry_enabled}
                aria-label={`retry_interval_seconds de l'étape ${step.order}`}
              />
            </div>

            <div>
              <Text type="secondary" style={{ fontSize: 12 }}>
                Backoff
              </Text>
              <InputNumber
                style={{ width: 160, marginTop: 4, display: 'block' }}
                min={1}
                step={0.1}
                value={step.retry_backoff_multiplier ?? null}
                onChange={(v) => onStepChange(index, 'retry_backoff_multiplier', v ?? null)}
                disabled={disabled || !step.retry_enabled}
                aria-label={`retry_backoff_multiplier de l'étape ${step.order}`}
              />
            </div>
          </Space>
        </Card>
      </Space>
    </Card>
  );
};

export const WorkflowStepsEditor: React.FC<WorkflowStepsEditorProps> = ({
  steps,
  onChange,
  loading = false,
  disabled = false,
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

  // Load eligible actions on mount
  useEffect(() => {
    setLoadingActions(true);
    setLoadError(null);
    getEligibleActionsForWorkflow()
      .then((actions) => {
        setEligibleActions(actions);
      })
      .catch((err) => {
        logger.error('Failed to load eligible actions for workflow', { error: err instanceof Error ? err.message : String(err) });
        // Improve error message to be more helpful
        let errorMessage = 'Impossible de charger les actions éligibles';
        if (err instanceof Error) {
          errorMessage = err.message;
          // If it's "Unknown error", provide more context
          if (err.message === 'Unknown error') {
            errorMessage = 'Erreur lors du chargement des actions éligibles. Vérifiez votre connexion et vos permissions DBOPS.';
          }
        }
        setLoadError(errorMessage);
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

/**
 * SortableStepCard — Carte d'étape réordonnables pour WorkflowStepsEditor (SOLID-FE-8).
 *
 * Extrait de WorkflowStepsEditor.tsx (Story 34-9) pour respecter SRP :
 * chaque composant a une seule responsabilité.
 *
 * Responsabilité : afficher et éditer une étape individuelle d'un workflow,
 * avec drag-and-drop via @dnd-kit.
 */

import React, { useMemo } from 'react';
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
  Tooltip,
  Spin,
  theme,
} from 'antd';
import { DeleteOutlined, HolderOutlined } from '@ant-design/icons';
import { useSortable } from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import type { WorkflowStepEditable } from './WorkflowStepsEditor';
import type { ActionListItem } from '../../types/api';
import { getStepLabel } from '../../utils/workflowStepLabels';

const { Text } = Typography;

export interface SortableStepCardProps {
  step: WorkflowStepEditable;
  index: number;
  eligibleActions: ActionListItem[];
  loadingActions: boolean;
  stepIdsFromEditor: string[];
  /** All steps for resolving step_id → action name in branch selects */
  allSteps: WorkflowStepEditable[];
  onStepChange: (index: number, field: keyof WorkflowStepEditable, value: unknown) => void;
  onRemoveStep: (index: number) => void;
  canRemove: boolean;
  hasError: boolean;
  disabled?: boolean;
}

/** Sortable step card using @dnd-kit. */
export const SortableStepCard: React.FC<SortableStepCardProps> = ({
  step,
  index,
  eligibleActions,
  loadingActions,
  stepIdsFromEditor,
  allSteps,
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
  /** Build branch options: step_id → display label — Story 57.19: uses centralized getStepLabel */
  const getBranchOptions = (excludeStepId: string | null | undefined) => {
    const ids = stepIdsFromEditor.filter((sid) => sid && sid !== excludeStepId);
    return ids.map((sid) => {
      const s = allSteps.find((st) => (st.step_id ?? st._tempId) === sid);
      if (!s) return { value: sid, label: sid };
      // Build label input: prefer resolved action_name from allSteps or from eligibleActions
      const action = eligibleActions.find((a) => a.id === s.referenced_action_id);
      const actionName = s.action_name ?? action?.name ?? undefined;
      const label = getStepLabel({ ...s, action_name: actionName });
      return { value: sid, label };
    });
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

          {/* Story 16.2: step_id read-only (auto-generated for branches/retry) */}
          {step.step_id && (
          <div style={{ marginBottom: 0, minWidth: 200 }}>
            <Text type="secondary" style={{ fontSize: 12 }}>
              ID d'étape
            </Text>
            <Tooltip title="Identifiant technique auto-généré pour les branches. Non modifiable.">
              <Input
                style={{ width: 200, marginTop: 4, display: 'block', fontSize: 11, fontFamily: 'monospace' }}
                value={stepIdValue}
                readOnly
                aria-label={`step_id de l'étape ${step.order}`}
              />
            </Tooltip>
          </div>
          )}
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
                style={{ width: 260, marginTop: 4, display: 'block' }}
                value={(step.on_success_step_id ?? EXIT_VALUE) as string}
                onChange={(v) => onStepChange(index, 'on_success_step_id', v === EXIT_VALUE ? null : v)}
                options={[
                  { value: EXIT_VALUE, label: '(fin du workflow)' },
                  ...getBranchOptions(step.step_id),
                ]}
                placeholder="Sélectionner une étape..."
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
                style={{ width: 260, marginTop: 4, display: 'block' }}
                value={(step.on_error_step_id ?? EXIT_VALUE) as string}
                onChange={(v) => onStepChange(index, 'on_error_step_id', v === EXIT_VALUE ? null : v)}
                options={[
                  { value: EXIT_VALUE, label: '(fin du workflow)' },
                  ...getBranchOptions(step.step_id),
                ]}
                placeholder="Sélectionner une étape..."
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

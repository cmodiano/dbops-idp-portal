/**
 * WorkflowStepsRenderer - Renders workflow step parameter forms.
 * Extracted from ParametersFormStep (Story 20.4, Task 2).
 *
 * Displays per-step parameter forms for workflow execution,
 * with validation errors and action loading states.
 *
 * Story 62.1: Added "Paramètres communs" section for parameters shared across ≥2 steps.
 */

import { memo, useRef } from 'react';
import { Form, Alert, Typography } from 'antd';
import type { FormRule as Rule } from 'antd';
import { useAuth } from '../../contexts/AuthContext';
import { InfoCircleOutlined } from '@ant-design/icons';
import type { CatalogActionDetail } from '../../services/catalog_service';
import type { InventoryItem } from '../../types/api';
import type { ParameterField } from '../../hooks/useDynamicForm';
import { extractParameterFields } from '../../hooks/useDynamicForm';
import { sanitizeDescription } from '../../utils/businessLanguage';
import { renderFieldInput } from './renderFieldInput';

const { Title } = Typography;

// ─── Story 62.1: Common parameter extraction ─────────────────────────────────

/** Unique key for a parameter (name + inventory discriminants). */
function paramKey(field: ParameterField): string {
  return `${field.name}|${field.inventorySource ?? ''}|${field.inventoryValueColumn ?? ''}`;
}

/**
 * Identifies parameters that appear in ≥2 workflow steps (same name + same inventory nature).
 * Returns the deduplicated list of common fields and a Set of their names for fast filtering.
 */
// eslint-disable-next-line react-refresh/only-export-components
export function extractCommonParameters(
  workflowStepActions: Record<number, CatalogActionDetail>,
  workflowSteps: Array<{ order: number; referenced_action_id?: number | null }>
): { commonFields: ParameterField[]; commonKeys: Set<string> } {
  const keyCount = new Map<string, { field: ParameterField; count: number }>();

  for (const step of workflowSteps) {
    const refId = step.referenced_action_id;
    if (refId == null) continue;
    const action = workflowStepActions[refId];
    if (!action) continue;
    const fields = extractParameterFields(action.parameters_schema ?? null);
    for (const field of fields) {
      const key = paramKey(field);
      const existing = keyCount.get(key);
      if (existing) existing.count += 1;
      else keyCount.set(key, { field, count: 1 });
    }
  }

  const commonFields: ParameterField[] = [];
  // Store paramKey strings (name|inventorySource|inventoryValueColumn) so that per-step
  // filtering uses the same discriminant as the grouping key. Filtering by name alone would
  // incorrectly hide non-common fields that share a name with a truly-common field of a
  // different inventory type.
  const commonKeys = new Set<string>();
  for (const { field, count } of keyCount.values()) {
    if (count >= 2) {
      commonFields.push(field);
      commonKeys.add(paramKey(field));
    }
  }

  return { commonFields, commonKeys };
}

// ─── Component ────────────────────────────────────────────────────────────────

export interface WorkflowStepsRendererProps {
  workflowSteps: Array<{ order: number; name: string | null; referenced_action_id?: number | null }>;
  workflowStepActions: Record<number, CatalogActionDetail>;
  loadingWorkflowStepActions: boolean;
  workflowStepActionsError: string | null;
  workflowValidationSummary: string | null;
  inventoryData: Record<string, InventoryItem[]>;
  inventoryWarnings: Record<string, boolean>;
  loadingInventory: boolean;
  /** Story 23.6 - Selected server names for filtering instances/databases. */
  selectedServerNames?: string[];
}

export const WorkflowStepsRenderer = memo(function WorkflowStepsRenderer({
  workflowSteps,
  workflowStepActions,
  loadingWorkflowStepActions,
  workflowStepActionsError,
  workflowValidationSummary,
  inventoryData,
  inventoryWarnings,
  loadingInventory,
  selectedServerNames = [],
}: WorkflowStepsRendererProps) {
  const firstFieldRef = useRef<HTMLElement | null>(null);
  const { isBusinessProfile } = useAuth();

  // Story 62.1: compute common parameters only when actions are fully loaded
  const { commonFields, commonKeys } = loadingWorkflowStepActions
    ? { commonFields: [], commonKeys: new Set<string>() }
    : extractCommonParameters(workflowStepActions, workflowSteps);

  /** Builds Ant Design Form rules for a parameter field. */
  function buildRules(field: ParameterField): Rule[] {
    const rules: Rule[] = [];
    if (field.required) rules.push({ required: true, message: `${field.label} est requis` });
    if (field.pattern) rules.push({ pattern: new RegExp(field.pattern), message: 'Format invalide' });
    if (field.minimum !== undefined) rules.push({ type: 'number', min: field.minimum, message: `Minimum: ${field.minimum}` });
    if (field.maximum !== undefined) rules.push({ type: 'number', max: field.maximum, message: `Maximum: ${field.maximum}` });
    return rules;
  }

  return (
    <div>
      {workflowValidationSummary && (
        <Alert
          type="error"
          showIcon
          title="Certaines étapes sont invalides"
          description={workflowValidationSummary}
          style={{ marginBottom: 16 }}
        />
      )}
      {workflowStepActionsError && (
        <Alert
          type="error"
          showIcon
          title="Impossible de charger les actions du workflow"
          description={workflowStepActionsError}
          style={{ marginBottom: 16 }}
        />
      )}
      {loadingWorkflowStepActions && (
        <Alert
          type="info"
          showIcon
          description="Chargement des étapes du workflow..."
          style={{ marginBottom: 16 }}
        />
      )}

      {/* Story 62.1 — Common parameters section */}
      {commonFields.length > 0 && (
        <div
          style={{
            border: '1px solid var(--ant-color-border-secondary)',
            borderRadius: 8,
            padding: 12,
            marginBottom: 12,
            background: 'var(--ant-color-bg-container)',
          }}
        >
          <Title level={5} style={{ marginTop: 0, marginBottom: 8 }}>
            Paramètres communs
          </Title>
          {commonFields.map((field: ParameterField) => {
            const rules = buildRules(field);
            const displayDescription = isBusinessProfile && field.description
              ? sanitizeDescription(field.description)
              : field.description;

            return (
              <Form.Item
                key={`shared-${field.name}`}
                name={['shared_parameters', field.name]}
                label={field.label}
                rules={rules}
                tooltip={displayDescription ? { title: displayDescription, icon: <InfoCircleOutlined /> } : undefined}
                style={{ marginBottom: 12 }}
              >
                {renderFieldInput(field, inventoryData, inventoryWarnings, loadingInventory, selectedServerNames)}
              </Form.Item>
            );
          })}
        </div>
      )}

      {/* Per-step parameter blocks */}
      {workflowSteps.map((step, stepIndex) => {
        const refAction = step.referenced_action_id != null ? workflowStepActions[step.referenced_action_id] : undefined;
        const actionName = refAction?.name || `Action #${step.referenced_action_id}`;
        const schema = refAction?.parameters_schema ?? null;
        // Story 62.1: exclude fields that are already shown in the common section
        const allFields = extractParameterFields(schema as Record<string, unknown> | null);
        const fields = allFields.filter((f) => !commonKeys.has(paramKey(f)));
        const stepKey = String(step.order);

        return (
          <div
            key={`${step.order}-${step.referenced_action_id}`}
            style={{
              border: '1px solid var(--ant-color-border-secondary)',
              borderRadius: 8,
              padding: 12,
              marginBottom: 12,
              background: 'var(--ant-color-bg-container)',
            }}
          >
            <Title level={5} style={{ marginTop: 0, marginBottom: 8 }}>
              Étape {step.order} — {actionName}
            </Title>

            {fields.length === 0 && allFields.length > 0 ? (
              // Story 62.1: all fields of this step are common
              <Alert
                type="info"
                showIcon
                description="Tous les paramètres de cette étape sont définis dans la section Paramètres communs."
              />
            ) : fields.length === 0 ? (
              <Alert type="info" showIcon description="Cette action n'a pas de paramètres" />
            ) : (
              fields.map((field: ParameterField, index: number) => {
                const rules = buildRules(field);
                const displayDescription = isBusinessProfile && field.description
                  ? sanitizeDescription(field.description)
                  : field.description;

                return (stepIndex === 0 && index === 0) ? (
                  <div key={`${step.order}-${field.name}`} ref={(ref) => { firstFieldRef.current = ref?.querySelector('input, select, [role="combobox"]') as HTMLElement; }}>
                    <Form.Item
                      name={['workflow_step_parameters', stepKey, 'parameters', field.name]}
                      label={field.label}
                      rules={rules}
                      tooltip={displayDescription ? { title: displayDescription, icon: <InfoCircleOutlined /> } : undefined}
                      style={{ marginBottom: 12 }}
                    >
                      {renderFieldInput(field, inventoryData, inventoryWarnings, loadingInventory, selectedServerNames)}
                    </Form.Item>
                  </div>
                ) : (
                  <Form.Item
                    key={`${step.order}-${field.name}`}
                    name={['workflow_step_parameters', stepKey, 'parameters', field.name]}
                    label={field.label}
                    rules={rules}
                    tooltip={displayDescription ? { title: displayDescription, icon: <InfoCircleOutlined /> } : undefined}
                    style={{ marginBottom: 12 }}
                  >
                    {renderFieldInput(field, inventoryData, inventoryWarnings, loadingInventory, selectedServerNames)}
                  </Form.Item>
                );
              })
            )}
          </div>
        );
      })}
    </div>
  );
});

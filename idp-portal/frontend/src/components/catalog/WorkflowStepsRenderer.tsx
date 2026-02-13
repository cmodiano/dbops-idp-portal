/**
 * WorkflowStepsRenderer - Renders workflow step parameter forms.
 * Extracted from ParametersFormStep (Story 20.4, Task 2).
 *
 * Displays per-step parameter forms for workflow execution,
 * with validation errors and action loading states.
 */

import { memo, useRef } from 'react';
import { Form, Alert, Typography } from 'antd';
import { InfoCircleOutlined } from '@ant-design/icons';
import type { FormInstance } from 'antd';
import type { CatalogActionDetail } from '../../services/catalog_service';
import type { InventoryItem } from '../../types/api';
import type { ParameterField } from '../../hooks/useDynamicForm';
import { extractParameterFields } from '../../hooks/useDynamicForm';
import { STYLE_TOKENS } from '../../theme/styleTokens';
import { sanitizeDescription } from '../../utils/businessLanguage';
import { renderFieldInput } from './renderFieldInput';

const { Title } = Typography;

export interface WorkflowStepsRendererProps {
  workflowSteps: Array<{ order: number; name: string | null; referenced_action_id: number }>;
  workflowStepActions: Record<number, CatalogActionDetail>;
  loadingWorkflowStepActions: boolean;
  workflowStepActionsError: string | null;
  workflowValidationSummary: string | null;
  variant: 'default' | 'simplified';
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
  variant,
  inventoryData,
  inventoryWarnings,
  loadingInventory,
  selectedServerNames = [],
}: WorkflowStepsRendererProps) {
  const firstFieldRef = useRef<HTMLElement | null>(null);

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

      {workflowSteps.map((step, stepIndex) => {
        const refAction = workflowStepActions[step.referenced_action_id];
        const actionName = refAction?.name || `Action #${step.referenced_action_id}`;
        const schema = refAction?.parameters_schema ?? null;
        const fields = extractParameterFields(schema as Record<string, unknown> | null);
        const stepKey = String(step.order);

        return (
          <div
            key={`${step.order}-${step.referenced_action_id}`}
            style={{
              border: `1px solid ${STYLE_TOKENS.borderColor}`,
              borderRadius: 8,
              padding: 12,
              marginBottom: 12,
              background: STYLE_TOKENS.surfaceColor,
            }}
          >
            <Title level={5} style={{ marginTop: 0, marginBottom: 8 }}>
              Étape {step.order} — {actionName}
            </Title>

            {fields.length === 0 ? (
              <Alert type="info" showIcon description="Cette action n'a pas de paramètres" />
            ) : (
              fields.map((field: ParameterField, index: number) => {
                const rules: unknown[] = [];
                if (field.required) rules.push({ required: true, message: `${field.label} est requis` });
                if (field.pattern) rules.push({ pattern: new RegExp(field.pattern), message: 'Format invalide' });
                if (field.minimum !== undefined) rules.push({ type: 'number', min: field.minimum, message: `Minimum: ${field.minimum}` });
                if (field.maximum !== undefined) rules.push({ type: 'number', max: field.maximum, message: `Maximum: ${field.maximum}` });

                const displayDescription = variant === 'simplified' && field.description
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

/**
 * ParametersFormStep - Step 2 of the execution wizard.
 * Story 17.2, Task 4.2. Refactored Story 20.4: workflow rendering extracted to WorkflowStepsRenderer.
 * Story 34.13 (SOLID-FE-7): Reduced from 15 to 11 props — 4 inventory props moved to
 * WizardExecutionContext (inventoryData, inventoryWarnings, loadingInventory, selectedServerNames)
 * and unused prop 'action' removed.
 *
 * Renders a dynamic form from action's parameters_schema or
 * delegates to WorkflowStepsRenderer for workflows.
 */

import { memo, useRef } from 'react';
import { Form, Alert } from 'antd';
import type { FormRule as Rule } from 'antd';
import { useAuth } from '../../contexts/AuthContext';
import { InfoCircleOutlined } from '@ant-design/icons';
import type { FormInstance } from 'antd';
import type { CatalogActionDetail } from '../../services/catalog_service';
import type { ParameterField } from '../../hooks/useDynamicForm';
import { sanitizeDescription } from '../../utils/businessLanguage';
import { renderFieldInput } from './renderFieldInput';
import { WorkflowStepsRenderer } from './WorkflowStepsRenderer';
import { useWizardExecutionContext } from '../../contexts/WizardExecutionContext';

import { STEP_DESCRIPTIONS_SIMPLIFIED } from '../../utils/stepDescriptions';

export interface ParametersFormStepProps {
  form: FormInstance;
  // 'action' removed — was unused in this component's implementation
  parameterFields: ParameterField[];
  parameters: Record<string, unknown>;
  onParametersChange: (values: Record<string, unknown>) => void;
  isWorkflow: boolean;
  workflowSteps: Array<{ order: number; name: string | null; referenced_action_id: number }>;
  workflowStepActions: Record<number, CatalogActionDetail>;
  loadingWorkflowStepActions: boolean;
  workflowStepActionsError: string | null;
  workflowValidationSummary: string | null;
  // 4 props moved to WizardExecutionContext:
  // inventoryData, inventoryWarnings, loadingInventory, selectedServerNames
}

export const ParametersFormStep = memo(function ParametersFormStep({
  form,
  parameterFields,
  parameters,
  onParametersChange,
  isWorkflow,
  workflowSteps,
  workflowStepActions,
  loadingWorkflowStepActions,
  workflowStepActionsError,
  workflowValidationSummary,
}: ParametersFormStepProps) {
  const {
    inventoryData,
    inventoryWarnings,
    loadingInventory,
    selectedServerNames,
  } = useWizardExecutionContext();
  const firstFieldRef = useRef<HTMLElement | null>(null);
  const { isBusinessProfile } = useAuth();

  return (
    <Form
      form={form}
      layout="vertical"
      clearOnDestroy={false}
      initialValues={parameters}
      onValuesChange={(_, allValues) => {
        onParametersChange({ ...(parameters || {}), ...(allValues || {}) });
      }}
    >
      {isBusinessProfile && (
        <Alert
          type="info"
          showIcon
          description={STEP_DESCRIPTIONS_SIMPLIFIED[1]}
          style={{ marginBottom: 16 }}
        />
      )}

      {isWorkflow ? (
        <WorkflowStepsRenderer
          workflowSteps={workflowSteps}
          workflowStepActions={workflowStepActions}
          loadingWorkflowStepActions={loadingWorkflowStepActions}
          workflowStepActionsError={workflowStepActionsError}
          workflowValidationSummary={workflowValidationSummary}
          inventoryData={inventoryData}
          inventoryWarnings={inventoryWarnings}
          loadingInventory={loadingInventory}
          selectedServerNames={selectedServerNames}
        />
      ) : (
        parameterFields.length === 0 ? (
          <Alert
            title="Aucun parametre requis"
            description={isBusinessProfile
              ? 'Aucune information supplementaire n\'est necessaire.'
              : 'Cette action ne necessite pas de parametres.'}
            type="info"
            showIcon
          />
        ) : (
          parameterFields.map((field, index) => {
            const rules: Rule[] = [];
            if (field.required) rules.push({ required: true, message: `${field.label} est requis` });
            if (field.pattern) rules.push({ pattern: new RegExp(field.pattern), message: 'Format invalide' });
            if (field.minimum !== undefined) rules.push({ type: 'number', min: field.minimum, message: `Minimum: ${field.minimum}` });
            if (field.maximum !== undefined) rules.push({ type: 'number', max: field.maximum, message: `Maximum: ${field.maximum}` });

            const displayDescription = isBusinessProfile && field.description
              ? sanitizeDescription(field.description)
              : field.description;

            return index === 0 ? (
              <div key={field.name} ref={(ref) => { firstFieldRef.current = ref?.querySelector('input, select, [role="combobox"]') as HTMLElement; }}>
                <Form.Item
                  name={field.name}
                  label={field.label}
                  rules={rules}
                  tooltip={displayDescription ? { title: displayDescription, icon: <InfoCircleOutlined /> } : undefined}
                >
                  {renderFieldInput(field, inventoryData, inventoryWarnings, loadingInventory, selectedServerNames)}
                </Form.Item>
              </div>
            ) : (
              <Form.Item
                key={field.name}
                name={field.name}
                label={field.label}
                rules={rules}
                tooltip={displayDescription ? { title: displayDescription, icon: <InfoCircleOutlined /> } : undefined}
              >
                {renderFieldInput(field, inventoryData, inventoryWarnings, loadingInventory, selectedServerNames)}
              </Form.Item>
            );
          })
        )
      )}
    </Form>
  );
});

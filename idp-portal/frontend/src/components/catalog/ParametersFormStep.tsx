/**
 * ParametersFormStep - Step 2 of the execution wizard.
 * Story 17.2, Task 4.2. Refactored Story 20.4: workflow rendering extracted to WorkflowStepsRenderer.
 *
 * Renders a dynamic form from action's parameters_schema or
 * delegates to WorkflowStepsRenderer for workflows.
 */

import { memo, useRef } from 'react';
import { Form, Alert } from 'antd';
import { InfoCircleOutlined } from '@ant-design/icons';
import type { FormInstance } from 'antd';
import type { CatalogActionDetail } from '../../services/catalog_service';
import type { InventoryItem } from '../../types/api';
import type { ParameterField } from '../../hooks/useDynamicForm';
import { sanitizeDescription } from '../../utils/businessLanguage';
import { renderFieldInput } from './renderFieldInput';
import { WorkflowStepsRenderer } from './WorkflowStepsRenderer';

const STEP_DESCRIPTIONS_SIMPLIFIED = [
  'Selectionnez la cible sur laquelle executer l\'action. L\'environnement sera derive automatiquement.',
  'Remplissez les informations necessaires. Tous les champs marques sont obligatoires.',
  'Verifiez que tout est correct avant de lancer l\'action.',
];

export interface ParametersFormStepProps {
  form: FormInstance;
  action: CatalogActionDetail;
  variant: 'default' | 'simplified';
  parameterFields: ParameterField[];
  parameters: Record<string, unknown>;
  onParametersChange: (values: Record<string, unknown>) => void;
  isWorkflow: boolean;
  workflowSteps: Array<{ order: number; name: string | null; referenced_action_id: number }>;
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

export const ParametersFormStep = memo(function ParametersFormStep({
  form,
  variant,
  parameterFields,
  parameters,
  onParametersChange,
  isWorkflow,
  workflowSteps,
  workflowStepActions,
  loadingWorkflowStepActions,
  workflowStepActionsError,
  workflowValidationSummary,
  inventoryData,
  inventoryWarnings,
  loadingInventory,
  selectedServerNames = [],
}: ParametersFormStepProps) {
  const firstFieldRef = useRef<HTMLElement | null>(null);

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
      {variant === 'simplified' && (
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
          variant={variant}
          inventoryData={inventoryData}
          inventoryWarnings={inventoryWarnings}
          loadingInventory={loadingInventory}
          selectedServerNames={selectedServerNames}
        />
      ) : (
        parameterFields.length === 0 ? (
          <Alert
            title="Aucun parametre requis"
            description={variant === 'simplified'
              ? 'Aucune information supplementaire n\'est necessaire.'
              : 'Cette action ne necessite pas de parametres.'}
            type="info"
            showIcon
          />
        ) : (
          parameterFields.map((field, index) => {
            const rules: unknown[] = [];
            if (field.required) rules.push({ required: true, message: `${field.label} est requis` });
            if (field.pattern) rules.push({ pattern: new RegExp(field.pattern), message: 'Format invalide' });
            if (field.minimum !== undefined) rules.push({ type: 'number', min: field.minimum, message: `Minimum: ${field.minimum}` });
            if (field.maximum !== undefined) rules.push({ type: 'number', max: field.maximum, message: `Maximum: ${field.maximum}` });

            const displayDescription = variant === 'simplified' && field.description
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

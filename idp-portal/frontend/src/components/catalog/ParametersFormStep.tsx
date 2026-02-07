/**
 * ParametersFormStep - Step 2 of the execution wizard.
 * Story 17.2, Task 4.2.
 *
 * Renders a dynamic form from action's parameters_schema or
 * per-step forms for workflows.
 */

import { memo, useRef } from 'react';
import {
  Form,
  Select,
  Input,
  InputNumber,
  Switch,
  DatePicker,
  Alert,
  Badge,
  Typography,
} from 'antd';
import { InfoCircleOutlined } from '@ant-design/icons';
import type { FormInstance } from 'antd';
import type { CatalogActionDetail } from '../../services/catalog_service';
import type { InventoryItem } from '../../types/api';
import type { ParameterField } from '../../hooks/useDynamicForm';
import { extractParameterFields } from '../../hooks/useDynamicForm';
import { STYLE_TOKENS } from '../../theme/styleTokens';
import { sanitizeDescription } from '../../utils/businessLanguage';

const { Title } = Typography;

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
}

function renderFieldInput(
  field: ParameterField,
  inventoryData: Record<string, InventoryItem[]>,
  inventoryWarnings: Record<string, boolean>,
  loadingInventory: boolean,
) {
  if (field.inventorySource && inventoryData[field.inventorySource]) {
    const hasWarning = inventoryWarnings[field.inventorySource];
    return (
      <div>
        <Select
          placeholder={`Selectionnez ${field.label.toLowerCase()}`}
          aria-label={field.label}
          loading={loadingInventory}
          options={inventoryData[field.inventorySource].map((item) => ({
            value: item.id,
            label: item.name,
          }))}
        />
        {hasWarning && (
          <Badge
            status="warning"
            text="Données inventaire temporairement indisponibles — dernières valeurs en cache"
            style={{ marginTop: 4, fontSize: '12px', color: '#faad14' }}
          />
        )}
      </div>
    );
  }

  switch (field.type) {
    case 'select':
      return (
        <Select
          placeholder={`Selectionnez ${field.label.toLowerCase()}`}
          aria-label={field.label}
          options={(field.enum || []).map((v) => ({ value: v, label: v }))}
        />
      );
    case 'number':
    case 'integer':
      return (
        <InputNumber
          style={{ width: '100%' }}
          aria-label={field.label}
          min={field.minimum}
          max={field.maximum}
          precision={field.type === 'integer' ? 0 : undefined}
        />
      );
    case 'boolean':
      return <Switch aria-label={field.label} />;
    case 'date':
    case 'date-time':
      return (
        <DatePicker
          style={{ width: '100%' }}
          showTime={field.type === 'date-time'}
          aria-label={field.label}
        />
      );
    case 'array':
      return (
        <Select
          mode="tags"
          placeholder={`Entrez ${field.label.toLowerCase()}`}
          aria-label={field.label}
        />
      );
    default:
      return <Input aria-label={field.label} />;
  }
}

export const ParametersFormStep = memo(function ParametersFormStep({
  form,
  action,
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
        <div>
          {workflowValidationSummary && (
            <Alert
              type="error"
              showIcon
              message="Certaines étapes sont invalides"
              description={workflowValidationSummary}
              style={{ marginBottom: 16 }}
            />
          )}
          {workflowStepActionsError && (
            <Alert
              type="error"
              showIcon
              message="Impossible de charger les actions du workflow"
              description={workflowStepActionsError}
              style={{ marginBottom: 16 }}
            />
          )}
          {loadingWorkflowStepActions && (
            <Alert
              type="info"
              showIcon
              message="Chargement des étapes du workflow..."
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
                  fields.map((field, index) => {
                    const rules: unknown[] = [];
                    if (field.required) rules.push({ required: true, message: `${field.label} est requis` });
                    if (field.pattern) rules.push({ pattern: new RegExp(field.pattern), message: 'Format invalide' });
                    if (field.minimum !== undefined) rules.push({ type: 'number', min: field.minimum, message: `Minimum: ${field.minimum}` });
                    if (field.maximum !== undefined) rules.push({ type: 'number', max: field.maximum, message: `Maximum: ${field.maximum}` });

                    const displayDescription = variant === 'simplified' && field.description
                      ? sanitizeDescription(field.description)
                      : field.description;

                    return (
                      <Form.Item
                        key={`${step.order}-${field.name}`}
                        name={['workflow_step_parameters', stepKey, 'parameters', field.name]}
                        label={field.label}
                        rules={rules}
                        tooltip={displayDescription ? { title: displayDescription, icon: <InfoCircleOutlined /> } : undefined}
                        style={{ marginBottom: 12 }}
                      >
                        {(stepIndex === 0 && index === 0) ? (
                          <div ref={(ref) => { firstFieldRef.current = ref?.querySelector('input, select, [role="combobox"]') as HTMLElement; }}>
                            {renderFieldInput(field, inventoryData, inventoryWarnings, loadingInventory)}
                          </div>
                        ) : (
                          renderFieldInput(field, inventoryData, inventoryWarnings, loadingInventory)
                        )}
                      </Form.Item>
                    );
                  })
                )}
              </div>
            );
          })}
        </div>
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

            return (
              <Form.Item
                key={field.name}
                name={field.name}
                label={field.label}
                rules={rules}
                tooltip={displayDescription ? { title: displayDescription, icon: <InfoCircleOutlined /> } : undefined}
              >
                {index === 0 ? (
                  <div ref={(ref) => { firstFieldRef.current = ref?.querySelector('input, select, [role="combobox"]') as HTMLElement; }}>
                    {renderFieldInput(field, inventoryData, inventoryWarnings, loadingInventory)}
                  </div>
                ) : (
                  renderFieldInput(field, inventoryData, inventoryWarnings, loadingInventory)
                )}
              </Form.Item>
            );
          })
        )
      )}
    </Form>
  );
});

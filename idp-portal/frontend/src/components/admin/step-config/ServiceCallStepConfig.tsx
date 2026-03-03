/**
 * ServiceCallStepConfig — Configuration pour les steps de type service_call (Story 57.13, AC3).
 *
 * Affiche : sélection integration_type, sélection operation (statique), éditeurs input/output_mapping, condition.
 *
 * SYNC: Les opérations sont hardcodées et doivent rester synchronisées avec
 * django_backend/executions/step_handlers/service_call_handler.py#_ALLOWED_OPERATIONS
 */

import React from 'react';
import { Divider, Select, Typography } from 'antd';
import type { WorkflowStepNodeData } from '../WorkflowStepNode';
import { KeyValueEditor } from './KeyValueEditor';
import { ConditionConfig } from './ConditionConfig';
import {
  SERVICE_CALL_OPERATIONS,
  INTEGRATION_LABELS,
  OPERATION_LABELS,
} from './serviceCallConstants';

const { Text } = Typography;

export interface ServiceCallStepConfigProps {
  data: WorkflowStepNodeData;
  onUpdate: (updates: Partial<WorkflowStepNodeData>) => void;
  disabled?: boolean;
}

export const ServiceCallStepConfig: React.FC<ServiceCallStepConfigProps> = ({
  data,
  onUpdate,
  disabled = false,
}) => {
  const availableOperations = data.integration_type
    ? (SERVICE_CALL_OPERATIONS[data.integration_type] ?? [])
    : [];

  const handleIntegrationChange = (value: string) => {
    onUpdate({ integration_type: value, operation: null });
  };

  return (
    <div data-testid="service-call-step-config">
      {/* Integration type */}
      <div style={{ marginBottom: 12 }}>
        <Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 4 }}>
          Type d'intégration <Text type="danger">*</Text>
        </Text>
        <Select
          style={{ width: '100%' }}
          size="small"
          value={data.integration_type ?? undefined}
          onChange={handleIntegrationChange}
          placeholder="Sélectionner une intégration"
          disabled={disabled}
          aria-label="Type d'intégration"
          options={Object.keys(INTEGRATION_LABELS).map((key) => ({
            value: key,
            label: INTEGRATION_LABELS[key],
          }))}
        />
      </div>

      {/* Operation */}
      <div style={{ marginBottom: 12 }}>
        <Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 4 }}>
          Opération <Text type="danger">*</Text>
        </Text>
        <Select
          style={{ width: '100%' }}
          size="small"
          value={data.operation ?? undefined}
          onChange={(value) => onUpdate({ operation: value })}
          placeholder="Sélectionner une opération"
          disabled={disabled || !data.integration_type}
          aria-label="Opération"
          options={availableOperations.map((op) => ({
            value: op,
            label: OPERATION_LABELS[op] ?? op,
          }))}
        />
      </div>

      <Divider style={{ margin: '8px 0' }} />

      {/* Input mapping */}
      <div style={{ marginBottom: 12 }}>
        <Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 4 }}>
          Mapping d'entrée (input_mapping)
        </Text>
        <KeyValueEditor
          value={data.input_mapping as Record<string, string> | null}
          onChange={(v) => onUpdate({ input_mapping: v })}
          disabled={disabled}
          keyPlaceholder="Paramètre"
          valuePlaceholder="Valeur / expression"
          data-testid="input-mapping-editor"
        />
      </div>

      {/* Output mapping */}
      <div style={{ marginBottom: 12 }}>
        <Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 4 }}>
          Mapping de sortie (output_mapping — JSONPath)
        </Text>
        <KeyValueEditor
          value={data.output_mapping ?? null}
          onChange={(v) => onUpdate({ output_mapping: v })}
          disabled={disabled}
          keyPlaceholder="Variable"
          valuePlaceholder="$.chemin.jsonpath"
          data-testid="output-mapping-editor"
        />
      </div>

      <Divider style={{ margin: '8px 0' }} />

      {/* Condition */}
      <ConditionConfig
        value={data.condition}
        onChange={(v) => onUpdate({ condition: v })}
        disabled={disabled}
      />
    </div>
  );
};

export default ServiceCallStepConfig;

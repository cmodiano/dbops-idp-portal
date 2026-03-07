/**
 * ServiceCallStepConfig — Configuration pour les steps de type service_call (Story 57.13, AC3).
 *
 * Affiche : sélection integration_type, sélection operation (statique), éditeurs input/output_mapping, condition.
 *
 * SYNC: Les opérations sont hardcodées et doivent rester synchronisées avec
 * django_backend/executions/step_handlers/service_call_handler.py#_ALLOWED_OPERATIONS
 */

import React, { useMemo } from 'react';
import { Divider, Select, Typography } from 'antd';
import type { WorkflowStepNodeData } from '../WorkflowStepNode';
import { KeyValueEditor } from './KeyValueEditor';
import { NotificationTemplateEditor } from './NotificationTemplateEditor';
import { ConditionConfig } from './ConditionConfig';
import { MappingHelpPopover } from './MappingHelpPopover';
import { useInputMappingWarnings } from '../../../hooks/useInputMappingWarnings';
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
  /** Story 57.20: Step options with readable labels for MappingHelpPopover. */
  availableStepOptions?: { value: string; label: string }[];
  /** Story 63.3: Step IDs disponibles pour le VariablePicker. */
  availableStepIds?: string[];
  /** Story 63.3: ID du workflow pour le VariablePicker. */
  workflowId?: number;
}

export const ServiceCallStepConfig: React.FC<ServiceCallStepConfigProps> = ({
  data,
  onUpdate,
  disabled = false,
  availableStepOptions,
  availableStepIds,
  workflowId,
}) => {
  const availableOperations = data.integration_type
    ? (SERVICE_CALL_OPERATIONS[data.integration_type] ?? [])
    : [];

  // Filtrer le step courant de la liste des étapes disponibles (AC4: "étapes précédentes")
  const filteredStepOptions = useMemo(
    () => availableStepOptions?.filter((s) => s.value !== data.step_id),
    [availableStepOptions, data.step_id],
  );

  const inputMappingWarnings = useInputMappingWarnings(
    data.input_mapping as Record<string, string> | null,
    filteredStepOptions,
  );

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
        {data.integration_type === 'notification' &&
        ['send_email', 'send_teams'].includes(data.operation ?? '') ? (
          <>
            <Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 8 }}>
              Configuration de la notification
            </Text>
            <NotificationTemplateEditor
              value={data.input_mapping as Record<string, string> | null}
              onChange={(v) => onUpdate({ input_mapping: v })}
              disabled={disabled}
              workflowId={workflowId}
              currentStepId={data.step_id ?? ''}
              availableStepIds={availableStepIds}
              operation={data.operation as 'send_email' | 'send_teams'}
            />
          </>
        ) : (
          <KeyValueEditor
            label="Mapping d'entrée (input_mapping)"
            helpContent={<MappingHelpPopover type="input" availableSteps={filteredStepOptions} />}
            value={data.input_mapping as Record<string, string> | null}
            onChange={(v) => onUpdate({ input_mapping: v })}
            disabled={disabled}
            keyPlaceholder="Paramètre"
            valuePlaceholder="{{ steps.<step_id>.<champ> }}"
            data-testid="input-mapping-editor"
            warnings={inputMappingWarnings}
            workflowId={workflowId}
            currentStepId={data.step_id}
            availableStepIds={availableStepIds}
          />
        )}
      </div>

      {/* Output mapping */}
      <div style={{ marginBottom: 12 }}>
        <KeyValueEditor
          label="Mapping de sortie (output_mapping)"
          helpContent={<MappingHelpPopover type="output" stepType="service_call" />}
          value={data.output_mapping ?? null}
          onChange={(v) => onUpdate({ output_mapping: v })}
          disabled={disabled}
          keyPlaceholder="Variable"
          valuePlaceholder="$.chemin.vers.champ"
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

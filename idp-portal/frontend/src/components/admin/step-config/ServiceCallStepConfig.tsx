/**
 * ServiceCallStepConfig — Configuration pour les steps de type service_call (Story 57.13, AC3).
 *
 * Affiche : sélection integration_type, sélection operation (statique), éditeurs input/output_mapping, condition.
 *
 * Story 82.7: Les opérations sont désormais fournies par l'API capabilities (GET /capabilities/integrations/)
 * avec fallback local via SERVICE_CALL_OPERATIONS si l'API est indisponible. Le fallback reste
 * synchronisé avec service_call_handler.py#_ALLOWED_OPERATIONS.
 */

import { useMemo } from 'react';
import type { FC } from 'react';
import { Divider, Select, Typography } from 'antd';
import type { WorkflowStepNodeData } from '../WorkflowStepNode';
import { KeyValueEditor } from './KeyValueEditor';
import { NotificationTemplateEditor } from './NotificationTemplateEditor';
import { ConditionConfig } from './ConditionConfig';
import { MappingHelpPopover } from './MappingHelpPopover';
import { useInputMappingWarnings } from '../../../hooks/useInputMappingWarnings';
import { useCapabilities } from '../../../hooks/useCapabilities';
import type { ServiceOperation } from '../../../services/capabilities_service';
import {
  SERVICE_CALL_OPERATIONS,
  INTEGRATION_LABELS,
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

export const ServiceCallStepConfig: FC<ServiceCallStepConfigProps> = ({
  data,
  onUpdate,
  disabled = false,
  availableStepOptions,
  availableStepIds,
  workflowId,
}) => {
  // Story 82.6: capacités backend pour les types et opérations d'intégration
  const { capabilities, loading: capabilitiesLoading } = useCapabilities();

  // Options integration_type : depuis le backend si dispo, sinon INTEGRATION_LABELS local (fallback)
  const integrationTypeOptions = useMemo(() => {
    if (capabilities?.services?.length) {
      return capabilities.services.map((s) => ({ value: s.code, label: s.display_name }));
    }
    return Object.keys(INTEGRATION_LABELS).map((key) => ({ value: key, label: INTEGRATION_LABELS[key] }));
  }, [capabilities]);

  // Opérations disponibles : depuis le backend si dispo (ServiceOperation[]), sinon fallback local
  const availableOperations = useMemo((): ServiceOperation[] => {
    if (!data.integration_type) return [];
    if (capabilities?.services?.length) {
      const svc = capabilities.services.find((s) => s.code === data.integration_type);
      // Si le service est trouvé dans le backend, utiliser ses opérations avec labels
      if (svc) return svc.operations;
      // integration_type non trouvé dans les services backend → fallback local
    }
    // Fallback : opérations locales sans labels riches (code = label)
    return (SERVICE_CALL_OPERATIONS[data.integration_type] ?? []).map((code) => ({ code, label: code }));
  }, [data.integration_type, capabilities]);

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
          loading={capabilitiesLoading}
          aria-label="Type d'intégration"
          options={integrationTypeOptions}
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
          loading={capabilitiesLoading}
          aria-label="Opération"
          options={availableOperations.map((op) => ({
            value: op.code,
            label: op.label,
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

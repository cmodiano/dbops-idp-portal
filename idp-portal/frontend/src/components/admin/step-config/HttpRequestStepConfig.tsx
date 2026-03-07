/**
 * HttpRequestStepConfig — Configuration pour les steps de type http_request (Story 57.13, AC6).
 *
 * Affiche : input url, sélection method, éditeur headers, éditeur params (dans input_mapping),
 * input request_timeout, éditeur output_mapping, condition.
 */

import React, { useMemo } from 'react';
import { Divider, Input, InputNumber, Select, Typography } from 'antd';
import type { WorkflowStepNodeData } from '../WorkflowStepNode';
import { KeyValueEditor } from './KeyValueEditor';
import { ConditionConfig } from './ConditionConfig';
import { MappingHelpPopover } from './MappingHelpPopover';
import { useInputMappingWarnings } from '../../../hooks/useInputMappingWarnings';

const { Text } = Typography;

const HTTP_METHODS = ['GET', 'POST', 'PUT', 'PATCH', 'DELETE'];

export interface HttpRequestStepConfigProps {
  data: WorkflowStepNodeData;
  onUpdate: (updates: Partial<WorkflowStepNodeData>) => void;
  disabled?: boolean;
  /** Story 57.20: Step options with readable labels for MappingHelpPopover. */
  availableStepOptions?: { value: string; label: string }[];
}

export const HttpRequestStepConfig: React.FC<HttpRequestStepConfigProps> = ({
  data,
  onUpdate,
  disabled = false,
  availableStepOptions,
}) => {
  // Filtrer le step courant de la liste des étapes disponibles (AC4: "étapes précédentes")
  const filteredStepOptions = useMemo(
    () => availableStepOptions?.filter((s) => s.value !== data.step_id),
    [availableStepOptions, data.step_id],
  );

  const inputMappingWarnings = useInputMappingWarnings(
    data.input_mapping as Record<string, string> | null,
    filteredStepOptions,
  );

  return (
    <div data-testid="http-request-step-config">
      {/* URL */}
      <div style={{ marginBottom: 12 }}>
        <Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 4 }}>
          URL <Text type="danger">*</Text>
        </Text>
        <Input
          size="small"
          value={data.url ?? ''}
          onChange={(e) => onUpdate({ url: e.target.value || null })}
          placeholder="https://api.exemple.com/endpoint"
          disabled={disabled}
          aria-label="URL de la requête HTTP"
        />
      </div>

      {/* Method */}
      <div style={{ marginBottom: 12 }}>
        <Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 4 }}>
          Méthode HTTP <Text type="danger">*</Text>
        </Text>
        <Select
          style={{ width: '100%' }}
          size="small"
          value={data.method ?? undefined}
          onChange={(value) => onUpdate({ method: value })}
          placeholder="Sélectionner une méthode"
          disabled={disabled}
          aria-label="Méthode HTTP"
          options={HTTP_METHODS.map((m) => ({ value: m, label: m }))}
        />
      </div>

      {/* Request timeout */}
      <div style={{ marginBottom: 12 }}>
        <Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 4 }}>
          Timeout de la requête (secondes)
        </Text>
        <InputNumber
          style={{ width: '100%' }}
          size="small"
          min={1}
          value={data.request_timeout ?? null}
          onChange={(v) => onUpdate({ request_timeout: v ?? null })}
          placeholder="ex: 30"
          disabled={disabled}
          aria-label="Timeout de la requête"
        />
      </div>

      <Divider style={{ margin: '8px 0' }} />

      {/* Headers */}
      <div style={{ marginBottom: 12 }}>
        <Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 4 }}>
          En-têtes HTTP (headers)
        </Text>
        <KeyValueEditor
          value={data.headers ?? null}
          onChange={(v) => onUpdate({ headers: v })}
          disabled={disabled}
          keyPlaceholder="Nom de l'en-tête"
          valuePlaceholder="Valeur"
          data-testid="headers-editor"
        />
      </div>

      {/* Params — stockés dans input_mapping pour http_request */}
      <div style={{ marginBottom: 12 }}>
        <KeyValueEditor
          label="Paramètres de requête (params)"
          helpContent={<MappingHelpPopover type="input" availableSteps={filteredStepOptions} />}
          value={data.input_mapping as Record<string, string> | null}
          onChange={(v) => onUpdate({ input_mapping: v })}
          disabled={disabled}
          keyPlaceholder="Paramètre"
          valuePlaceholder="{{ steps.<step_id>.<champ> }}"
          data-testid="params-editor"
          warnings={inputMappingWarnings}
        />
      </div>

      {/* Output mapping */}
      <div style={{ marginBottom: 12 }}>
        <KeyValueEditor
          label="Mapping de sortie (output_mapping)"
          helpContent={<MappingHelpPopover type="output" stepType="http_request" />}
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

export default HttpRequestStepConfig;

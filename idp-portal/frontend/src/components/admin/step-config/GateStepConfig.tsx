/**
 * GateStepConfig — Configuration pour les steps de type gate (Story 57.13, AC5).
 *
 * Affiche : sélection gate_type, input timeout, sélection on_timeout (FAIL/SKIP),
 * multi-select context_from et approver_profile_ids déclenchés par config_schema du variant
 * sélectionné (Story 83-9 — logique déclarative, suppression des branches hardcodées gate_type=approval).
 */

import { type FC, useMemo } from 'react';
import { Input, Select, Typography } from 'antd';
import type { WorkflowStepNodeData } from '../WorkflowStepNode';
import { useApproverProfiles } from '../../../hooks/useApproverProfiles';
import { useWorkflowStepCapabilities } from '../../../hooks/useWorkflowStepCapabilities';
import { SchemaFormRenderer } from '../../shared/SchemaFormRenderer';

const { Text } = Typography;

export interface GateStepConfigProps {
  data: WorkflowStepNodeData;
  onUpdate: (updates: Partial<WorkflowStepNodeData>) => void;
  disabled?: boolean;
  /** Step IDs disponibles dans le workflow courant (pour context_from) — fallback si availableStepOptions non fourni */
  availableStepIds?: string[];
  /** Story 57.19: Pre-computed step options with readable labels (for context_from) */
  availableStepOptions?: { value: string; label: string }[];
}

const ON_TIMEOUT_OPTIONS = [
  { value: 'FAIL', label: 'Échouer le workflow' },
  { value: 'SKIP', label: 'Ignorer (continuer)' },
];

export const GateStepConfig: FC<GateStepConfigProps> = ({
  data,
  onUpdate,
  disabled = false,
  availableStepIds = [],
  availableStepOptions,
}) => {
  // Story 57.19: Use pre-computed options with labels if available, fallback to raw IDs
  const stepOptions = availableStepOptions ?? availableStepIds.map((id) => ({ value: id, label: id }));
  // Story 83-12: gate variants depuis le backend — résilience technique uniquement (liste vide si API indisponible, pas de fallback métier)
  const { gateVariants, loading: gateLoading } = useWorkflowStepCapabilities();
  const gateOptions = gateVariants.map((v) => ({ value: v.code, label: v.label }));

  // Story 83-9: Résoudre le config_schema du gate variant sélectionné (déclaratif)
  const selectedVariant = gateVariants.find((v) => v.code === data.gate_type);
  const configSchema = (selectedVariant?.config_schema ?? {}) as {
    properties?: Record<string, unknown>;
  };
  const hasApproverProfiles = !!configSchema.properties?.approver_profile_ids;

  const { approverProfileOptions, loading: approverProfilesLoading } = useApproverProfiles(hasApproverProfiles);

  // T4 — Bridge gateConfigValue / handleGateConfigChange (Story 84-5, AC2)
  const gateConfigValue: Record<string, unknown> = {
    context_from: data.context_from,
    approver_profile_ids: data.approver_profile_ids,
  };

  const handleGateConfigChange = (newValues: Record<string, unknown>) => {
    onUpdate({
      context_from: (newValues.context_from as string[] | null) ?? null,
      approver_profile_ids: (newValues.approver_profile_ids as number[] | null) ?? null,
    });
  };

  // T5 — Custom renderers pour les champs à source de données externe (Story 84-5, AC3)
  const gateCustomRenderers = useMemo(() => ({
    context_from: (value: unknown, onChange: (v: unknown) => void, isDisabled: boolean) => (
      <Select
        mode="multiple"
        style={{ width: '100%' }}
        size="small"
        value={(value as string[] | null) ?? []}
        onChange={(vals: string[]) => onChange(vals.length > 0 ? vals : null)}
        placeholder="Sélectionner des étapes"
        disabled={isDisabled}
        aria-label="Contexte pour l'approbateur"
        options={stepOptions}
      />
    ),
    approver_profile_ids: (value: unknown, onChange: (v: unknown) => void, isDisabled: boolean) => (
      <Select
        mode="multiple"
        style={{ width: '100%' }}
        size="small"
        loading={approverProfilesLoading}
        value={(value as number[] | null) ?? []}
        onChange={(vals: number[]) => onChange(vals.length > 0 ? vals : null)}
        placeholder="Tous les profils approbateurs éligibles (si vide)"
        disabled={isDisabled}
        aria-label="Profils approbateurs"
        options={approverProfileOptions}
      />
    ),
  }), [stepOptions, approverProfileOptions, approverProfilesLoading]);

  return (
    <div data-testid="gate-step-config">
      {/* Gate type */}
      <div style={{ marginBottom: 12 }}>
        <Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 4 }}>
          Type de gate <Text type="danger">*</Text>
        </Text>
        <Select
          style={{ width: '100%' }}
          size="small"
          value={data.gate_type ?? undefined}
          onChange={(value) => {
            // Story 84-5, AC4 : reset générique — itère les clés du schema
            const newVariant = gateVariants.find((v) => v.code === value);
            const newSchema = (newVariant?.config_schema ?? {}) as { properties?: Record<string, unknown> };
            const newProperties = newSchema.properties ?? {};

            const resetUpdates: Partial<Record<string, null>> = {};
            for (const key of Object.keys(configSchema.properties ?? {})) {
              if (!newProperties[key]) {
                resetUpdates[key] = null;
              }
            }

            onUpdate({
              gate_type: value,
              context_from: resetUpdates.context_from !== undefined ? null : data.context_from,
              approver_profile_ids: resetUpdates.approver_profile_ids !== undefined ? null : data.approver_profile_ids,
            });
          }}
          placeholder="Sélectionner un type"
          disabled={disabled}
          aria-label="Type de gate"
          loading={gateLoading}
          options={gateOptions}
        />
      </div>

      {/* Timeout */}
      <div style={{ marginBottom: 12 }}>
        <Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 4 }}>
          Délai d'attente (ex: 24h, 30m)
        </Text>
        <Input
          size="small"
          value={data.timeout ?? ''}
          onChange={(e) => onUpdate({ timeout: e.target.value || null })}
          placeholder="ex: 24h"
          disabled={disabled}
          aria-label="Délai d'attente"
        />
        <Text type="secondary" style={{ fontSize: 11, marginTop: 4, display: 'block' }}>
          Laisser vide = délai infini (pas de timeout automatique)
        </Text>
      </div>

      {/* On timeout action */}
      <div style={{ marginBottom: 12 }}>
        <Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 4 }}>
          Action si timeout dépassé
        </Text>
        <Select
          style={{ width: '100%' }}
          size="small"
          value={data.on_timeout ?? 'FAIL'}
          onChange={(value) => onUpdate({ on_timeout: value })}
          disabled={disabled}
          aria-label="Action si timeout"
          options={ON_TIMEOUT_OPTIONS}
        />
      </div>

      {/* Champs config_schema — Story 84-5, AC2/AC3 : route via SchemaFormRenderer avec custom renderers */}
      <SchemaFormRenderer // B.5 done (story 84-5)
        schema={configSchema as Record<string, unknown>}
        value={gateConfigValue}
        onChange={handleGateConfigChange}
        disabled={disabled}
        customRenderers={gateCustomRenderers}
      />
    </div>
  );
};

export default GateStepConfig;

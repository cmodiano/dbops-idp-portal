/**
 * GateStepConfig — Configuration pour les steps de type gate (Story 57.13, AC5).
 *
 * Affiche : sélection gate_type, input timeout, sélection on_timeout (FAIL/SKIP),
 * multi-select context_from et approver_profile_ids déclenchés par config_schema du variant
 * sélectionné (Story 83-9 — logique déclarative, suppression des branches hardcodées gate_type=approval).
 */

import type { FC } from 'react';
import { Input, Select, Typography } from 'antd';
import type { WorkflowStepNodeData } from '../WorkflowStepNode';
import { useApproverProfiles } from '../../../hooks/useApproverProfiles';
import { useWorkflowStepCapabilities } from '../../../hooks/useWorkflowStepCapabilities';

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
  // Story 82.6: gate variants depuis le backend (fallback local si API indisponible)
  const { gateVariants, loading: gateLoading } = useWorkflowStepCapabilities();
  const gateOptions = gateVariants.map((v) => ({ value: v.code, label: v.label }));

  // Story 83-9: Résoudre le config_schema du gate variant sélectionné (déclaratif)
  const selectedVariant = gateVariants.find((v) => v.code === data.gate_type);
  const configSchema = (selectedVariant?.config_schema ?? {}) as {
    properties?: Record<string, unknown>;
  };
  const hasContextFrom = !!configSchema.properties?.context_from;
  const hasApproverProfiles = !!configSchema.properties?.approver_profile_ids;

  const { approverProfileOptions, loading: approverProfilesLoading } = useApproverProfiles(hasApproverProfiles);

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
            // Story 83-9, AC5 : réinitialiser les champs non déclarés par le nouveau gate variant
            const newVariant = gateVariants.find((v) => v.code === value);
            const newSchema = (newVariant?.config_schema ?? {}) as { properties?: Record<string, unknown> };
            onUpdate({
              gate_type: value,
              context_from: newSchema.properties?.context_from ? data.context_from : null,
              approver_profile_ids: newSchema.properties?.approver_profile_ids ? data.approver_profile_ids : null,
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

      {/* context_from — déclaratif : rendu si config_schema le déclare (Story 83-9, AC3) */}
      {hasContextFrom && (
        <div style={{ marginBottom: 12 }}>
          <Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 4 }}>
            Contexte à afficher à l'approbateur (context_from)
          </Text>
          <Select
            mode="multiple"
            style={{ width: '100%' }}
            size="small"
            value={data.context_from ?? []}
            onChange={(value) => onUpdate({ context_from: value.length > 0 ? value : null })}
            placeholder="Sélectionner des étapes"
            disabled={disabled}
            aria-label="Contexte pour l'approbateur"
            options={stepOptions}
          />
          <Text type="secondary" style={{ fontSize: 11, marginTop: 4, display: 'block' }}>
            Step IDs dont le résultat sera visible par l'approbateur
          </Text>
        </div>
      )}

      {/* approver_profile_ids — déclaratif : rendu si config_schema le déclare (Story 83-9, AC3) */}
      {hasApproverProfiles && (
        <div style={{ marginBottom: 12 }}>
          <Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 4 }}>
            Profils approbateurs autorisés
          </Text>
          <Select
            mode="multiple"
            style={{ width: '100%' }}
            size="small"
            loading={approverProfilesLoading}
            value={data.approver_profile_ids ?? []}
            onChange={(value: number[]) =>
              onUpdate({ approver_profile_ids: value.length > 0 ? value : null })
            }
            placeholder="Tous les profils approbateurs éligibles (si vide)"
            disabled={disabled}
            aria-label="Profils approbateurs"
            options={approverProfileOptions}
          />
          <Text type="secondary" style={{ fontSize: 11, marginTop: 4, display: 'block' }}>
            Laisser vide pour autoriser tous les profils avec is_approver=true
          </Text>
        </div>
      )}
    </div>
  );
};

export default GateStepConfig;

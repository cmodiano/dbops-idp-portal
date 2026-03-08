/**
 * GateStepConfig — Configuration pour les steps de type gate (Story 57.13, AC5).
 *
 * Affiche : sélection gate_type, input timeout, sélection on_timeout (FAIL/SKIP),
 * multi-select context_from (step_ids du workflow courant, si gate_type=approval),
 * multi-select approver_profile_ids (profils approbateurs, si gate_type=approval — Story 58.4 AC2).
 */

import React from 'react';
import { Input, Select, Typography } from 'antd';
import type { WorkflowStepNodeData } from '../WorkflowStepNode';
import { useApproverProfiles } from '../../../hooks/useApproverProfiles';

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

const GATE_TYPE_OPTIONS = [
  { value: 'maintenance_window', label: 'Fenêtre de maintenance' },
  { value: 'approval', label: 'Approbation manuelle' },
];

const ON_TIMEOUT_OPTIONS = [
  { value: 'FAIL', label: 'Échouer le workflow' },
  { value: 'SKIP', label: 'Ignorer (continuer)' },
];

export const GateStepConfig: React.FC<GateStepConfigProps> = ({
  data,
  onUpdate,
  disabled = false,
  availableStepIds = [],
  availableStepOptions,
}) => {
  // Story 57.19: Use pre-computed options with labels if available, fallback to raw IDs
  const stepOptions = availableStepOptions ?? availableStepIds.map((id) => ({ value: id, label: id }));
  const { approverProfileOptions, loading: approverProfilesLoading } = useApproverProfiles(data.gate_type === 'approval');

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
          onChange={(value) => onUpdate({ gate_type: value, context_from: value !== 'approval' ? null : data.context_from })}
          placeholder="Sélectionner un type"
          disabled={disabled}
          aria-label="Type de gate"
          options={GATE_TYPE_OPTIONS}
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

      {/* context_from — only for approval gates */}
      {data.gate_type === 'approval' && (
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

      {/* approver_profile_ids — only for approval gates — Story 58.4 AC2 */}
      {data.gate_type === 'approval' && (
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

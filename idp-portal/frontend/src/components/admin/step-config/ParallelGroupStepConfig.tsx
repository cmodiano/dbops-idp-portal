/**
 * ParallelGroupStepConfig — Configuration du step parallel_group (Story 65.5).
 *
 * Permet de sélectionner les step_id à exécuter en parallèle.
 * Les connexions on_all_success / on_any_error se gèrent via les handles du canvas.
 */

import React, { useMemo } from 'react';
import { Select, Typography, Alert } from 'antd';
import type { WorkflowStepNodeData } from '../WorkflowStepNode';

const { Text } = Typography;

export interface ParallelGroupStepConfigProps {
  data: WorkflowStepNodeData;
  onUpdate: (updates: Partial<WorkflowStepNodeData>) => void;
  disabled?: boolean;
  /** Story 57.19 compatible: options avec labels lisibles */
  availableStepOptions?: { value: string; label: string }[];
}

export const ParallelGroupStepConfig: React.FC<ParallelGroupStepConfigProps> = ({
  data,
  onUpdate,
  disabled = false,
  availableStepOptions = [],
}) => {
  // Filtrer le step courant des options disponibles (auto-référence interdite)
  const filteredOptions = useMemo(
    () => availableStepOptions.filter((opt) => opt.value !== data.step_id),
    [availableStepOptions, data.step_id],
  );

  const parallelSteps = data.parallel_steps ?? [];
  const hasLessThanTwo = parallelSteps.length < 2;

  return (
    <div data-testid="parallel-group-step-config">
      {/* Sélection parallel_steps */}
      <div style={{ marginBottom: 12 }}>
        <Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 4 }}>
          Étapes à exécuter en parallèle <Text type="danger">*</Text>
        </Text>
        <Select
          mode="multiple"
          style={{ width: '100%' }}
          size="small"
          value={parallelSteps}
          onChange={(value: string[]) => onUpdate({ parallel_steps: value })}
          placeholder="Sélectionner au moins 2 étapes"
          disabled={disabled}
          aria-label="Étapes parallèles"
          options={filteredOptions}
          status={hasLessThanTwo ? 'error' : undefined}
        />
        {hasLessThanTwo && (
          <Text type="danger" style={{ fontSize: 11, display: 'block', marginTop: 4 }} role="alert">
            Un groupe parallèle requiert au moins 2 étapes
          </Text>
        )}
      </div>

      {/* Note connexions canvas */}
      <Alert
        type="info"
        showIcon
        style={{ marginBottom: 8 }}
        title="Les connexions succès / erreur se définissent directement sur le canvas en reliant les ports du nœud."
      />

      {/* Note fail-fast */}
      <Alert
        type="warning"
        showIcon
        style={{ marginBottom: 8 }}
        title="Comportement fail-fast : si un sous-step échoue, le groupe entier suit le chemin erreur."
      />
    </div>
  );
};

export default ParallelGroupStepConfig;

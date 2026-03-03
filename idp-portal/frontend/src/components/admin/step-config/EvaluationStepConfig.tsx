/**
 * EvaluationStepConfig — Configuration pour les steps de type evaluation (Story 57.13, AC4).
 *
 * Affiche : sélection policy_id (fetch depuis /admin/business-rule-policies/?is_active=true),
 * éditeur input_mapping, condition.
 */

import React, { useEffect, useState } from 'react';
import { Alert, Divider, Select, Spin, Typography } from 'antd';
import type { WorkflowStepNodeData } from '../WorkflowStepNode';
import type { BusinessRulePolicyListItem } from '../../../types/api';
import { getBusinessRulePolicies } from '../../../services/business_rules_service';
import { KeyValueEditor } from './KeyValueEditor';
import { ConditionConfig } from './ConditionConfig';
import logger from '../../../services/logger';

const { Text } = Typography;

export interface EvaluationStepConfigProps {
  data: WorkflowStepNodeData;
  onUpdate: (updates: Partial<WorkflowStepNodeData>) => void;
  disabled?: boolean;
}

export const EvaluationStepConfig: React.FC<EvaluationStepConfigProps> = ({
  data,
  onUpdate,
  disabled = false,
}) => {
  const [policies, setPolicies] = useState<BusinessRulePolicyListItem[]>([]);
  const [loadingPolicies, setLoadingPolicies] = useState(false);
  const [policiesError, setPoliciesError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoadingPolicies(true);
    setPoliciesError(null);
    getBusinessRulePolicies({ is_active: true })
      .then((response) => {
        if (!cancelled) setPolicies(response.data ?? []);
      })
      .catch((err) => {
        if (cancelled) return;
        const msg = err instanceof Error ? err.message : 'Erreur chargement politiques';
        logger.error('EvaluationStepConfig: failed to load policies', { error: msg });
        setPoliciesError(msg);
      })
      .finally(() => { if (!cancelled) setLoadingPolicies(false); });
    return () => { cancelled = true; };
  }, []);

  return (
    <div data-testid="evaluation-step-config">
      {/* Policy selection */}
      <div style={{ marginBottom: 12 }}>
        <Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 4 }}>
          Politique de règles métier <Text type="danger">*</Text>
        </Text>
        {loadingPolicies && <Spin size="small" />}
        {policiesError && (
          <Alert type="error" title={policiesError} showIcon style={{ marginBottom: 8 }} />
        )}
        {!loadingPolicies && (
          <Select
            style={{ width: '100%' }}
            size="small"
            value={data.policy_id ?? undefined}
            onChange={(value) => onUpdate({ policy_id: value })}
            placeholder="Sélectionner une politique"
            disabled={disabled || loadingPolicies}
            aria-label="Politique de règles métier"
            showSearch
            filterOption={(input, option) =>
              (option?.label as string ?? '').toLowerCase().includes(input.toLowerCase())
            }
            options={policies.map((p) => ({
              value: p.id,
              label: p.name,
            }))}
          />
        )}
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

export default EvaluationStepConfig;

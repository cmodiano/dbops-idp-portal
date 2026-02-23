/**
 * Story 28.4, AC#6: Sélecteur de règle métier pour le ActionWizard.
 * Uniquement règles prédéfinies (catalogue), filtrées par plateforme d'exécution (step_type).
 */

import { useState, useEffect, useCallback } from 'react';
import { Radio, Select, Space, Button, Modal, Typography, Tag } from 'antd';
import { EyeOutlined } from '@ant-design/icons';
import type { BusinessRulePolicyListItem, BusinessRulePoliciesData } from '../../types/api';
import { getBusinessRulePolicies } from '../../services/business_rules_service';

const { Text } = Typography;

type PolicyMode = 'none' | 'predefined';

export interface BusinessRulePolicySelectorProps {
  /** Current selected predefined policy ID (null if none). */
  policyId: number | null;
  /** Called when predefined policy is selected or cleared. */
  onPolicyIdChange: (id: number | null) => void;
  /** step_type (e.g. aap, terraform_cloud, azure_devops) to filter rules by execution platform. When empty, list is empty and message is shown. */
  stepType?: string | null;
  disabled?: boolean;
}

export function BusinessRulePolicySelector({
  policyId,
  onPolicyIdChange,
  stepType,
  disabled,
}: BusinessRulePolicySelectorProps) {
  const [policies, setPolicies] = useState<BusinessRulePolicyListItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [previewJson, setPreviewJson] = useState<BusinessRulePoliciesData | null>(null);
  const [previewName, setPreviewName] = useState('');

  const [mode, setMode] = useState<PolicyMode>(policyId ? 'predefined' : 'none');
  useEffect(() => {
    setMode(policyId ? 'predefined' : 'none');
  }, [policyId]);

  const fetchPolicies = useCallback(async () => {
    if (!stepType?.trim()) {
      setPolicies([]);
      return;
    }
    setLoading(true);
    try {
      const response = await getBusinessRulePolicies({
        is_active: true,
        step_type: stepType.trim(),
      });
      setPolicies(response.data ?? []);
    } catch {
      setPolicies([]);
    } finally {
      setLoading(false);
    }
  }, [stepType]);

  useEffect(() => {
    fetchPolicies();
  }, [fetchPolicies]);

  const handleModeChange = (newMode: PolicyMode) => {
    setMode(newMode);
    if (newMode === 'none') {
      onPolicyIdChange(null);
    }
  };

  const handlePolicySelect = (value: number | null) => {
    onPolicyIdChange(value ?? null);
  };

  const handlePreview = (policyItem: BusinessRulePolicyListItem) => {
    import('../../services/business_rules_service').then(({ getBusinessRulePolicy }) => {
      getBusinessRulePolicy(policyItem.id)
        .then((detail) => {
          setPreviewJson(detail.policy_json);
          setPreviewName(detail.name);
        })
        .catch(() => {
          setPreviewJson(null);
          setPreviewName('');
        });
    });
  };

  const selectedPolicy = policies.find(p => p.id === policyId);
  const hasStepType = !!stepType?.trim();

  return (
    <div>
      <Radio.Group
        value={mode}
        onChange={(e) => handleModeChange(e.target.value)}
        disabled={disabled}
        style={{ marginBottom: 12 }}
      >
        <Radio value="none">Aucune</Radio>
        <Radio value="predefined">Règle prédéfinie</Radio>
      </Radio.Group>

      {mode === 'predefined' && (
        <Space direction="vertical" style={{ width: '100%' }}>
          {!hasStepType ? (
            <Text type="secondary">
              Sélectionnez une intégration (plateforme d'exécution) pour afficher les règles métier disponibles.
            </Text>
          ) : (
            <>
              <Space style={{ width: '100%' }}>
                <Select
                  value={policyId ?? undefined}
                  onChange={handlePolicySelect}
                  placeholder="Sélectionner une règle..."
                  loading={loading}
                  disabled={disabled}
                  allowClear
                  style={{ minWidth: 350 }}
                  options={policies.map(p => ({
                    value: p.id,
                    label: (
                      <Space>
                        <span>{p.name}</span>
                        {p.step_type && <Tag>{p.step_type}</Tag>}
                      </Space>
                    ),
                  }))}
                  optionFilterProp="label"
                  filterOption={(input, option) => {
                    const policy = policies.find(p => p.id === option?.value);
                    return policy?.name.toLowerCase().includes(input.toLowerCase()) ?? false;
                  }}
                />
                {selectedPolicy && (
                  <Button
                    icon={<EyeOutlined />}
                    size="small"
                    onClick={() => handlePreview(selectedPolicy)}
                    disabled={disabled}
                  >
                    Voir JSON
                  </Button>
                )}
              </Space>
              {selectedPolicy?.description && (
                <Text type="secondary" style={{ fontSize: 12 }}>{selectedPolicy.description}</Text>
              )}
              {hasStepType && policies.length === 0 && !loading && (
                <Text type="secondary">
                  Aucune règle prédéfinie pour cette plateforme. Créez-en dans Admin → Règles métier.
                </Text>
              )}
            </>
          )}
        </Space>
      )}

      <Modal
        title={`Règle : ${previewName}`}
        open={!!previewJson}
        onCancel={() => setPreviewJson(null)}
        footer={<Button onClick={() => setPreviewJson(null)}>Fermer</Button>}
        width={600}
      >
        <pre style={{ fontFamily: 'monospace', fontSize: 12, maxHeight: 400, overflow: 'auto' }}>
          {previewJson ? JSON.stringify(previewJson, null, 2) : ''}
        </pre>
      </Modal>
    </div>
  );
}

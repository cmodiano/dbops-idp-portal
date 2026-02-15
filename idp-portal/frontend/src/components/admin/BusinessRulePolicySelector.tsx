/**
 * Story 28.4, AC#6: S\u00e9lecteur de r\u00e8gle m\u00e9tier pour le ActionWizard.
 *
 * Radio.Group avec 3 options : Aucune, R\u00e8gle pr\u00e9d\u00e9finie (Select), R\u00e8gle personnalis\u00e9e (inline JSON).
 */

import { useState, useEffect, useCallback } from 'react';
import { Radio, Select, Space, Button, Modal, Typography, Tag } from 'antd';
import { EyeOutlined } from '@ant-design/icons';
import type { BusinessRulePolicyListItem, BusinessRulePoliciesData } from '../../types/api';
import { getBusinessRulePolicies } from '../../services/business_rules_service';
import { BusinessRulePoliciesEditor } from './BusinessRulePoliciesEditor';

const { Text } = Typography;

type PolicyMode = 'none' | 'predefined' | 'inline';

export interface BusinessRulePolicySelectorProps {
  /** Current selected predefined policy ID (null if none or inline). */
  policyId: number | null;
  /** Current inline JSON string (empty if none or predefined). */
  inlineJson: string;
  /** Called when predefined policy is selected or cleared. */
  onPolicyIdChange: (id: number | null) => void;
  /** Called when inline JSON changes. */
  onInlineJsonChange: (json: string) => void;
  disabled?: boolean;
}

export function BusinessRulePolicySelector({
  policyId,
  inlineJson,
  onPolicyIdChange,
  onInlineJsonChange,
  disabled,
}: BusinessRulePolicySelectorProps) {
  const [policies, setPolicies] = useState<BusinessRulePolicyListItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [previewJson, setPreviewJson] = useState<BusinessRulePoliciesData | null>(null);
  const [previewName, setPreviewName] = useState('');

  // Derive mode from current state
  const mode: PolicyMode = policyId ? 'predefined' : inlineJson.trim() ? 'inline' : 'none';

  const fetchPolicies = useCallback(async () => {
    setLoading(true);
    try {
      const response = await getBusinessRulePolicies({ is_active: true });
      setPolicies(response.data ?? []);
    } catch {
      setPolicies([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchPolicies();
  }, [fetchPolicies]);

  const handleModeChange = (newMode: PolicyMode) => {
    if (newMode === 'none') {
      onPolicyIdChange(null);
      onInlineJsonChange('');
    } else if (newMode === 'predefined') {
      onInlineJsonChange('');
    } else if (newMode === 'inline') {
      onPolicyIdChange(null);
    }
  };

  const handlePolicySelect = (value: number | null) => {
    onPolicyIdChange(value ?? null);
    onInlineJsonChange('');
  };

  const handlePreview = (policyItem: BusinessRulePolicyListItem) => {
    // MEDIUM-2: Add error handling for preview fetch
    import('../../services/business_rules_service').then(({ getBusinessRulePolicy }) => {
      getBusinessRulePolicy(policyItem.id)
        .then((detail) => {
          setPreviewJson(detail.policy_json);
          setPreviewName(detail.name);
        })
        .catch(() => {
          // Silently fail — preview modal won't open
          setPreviewJson(null);
          setPreviewName('');
        });
    });
  };

  const selectedPolicy = policies.find(p => p.id === policyId);

  return (
    <div>
      <Radio.Group
        value={mode}
        onChange={(e) => handleModeChange(e.target.value)}
        disabled={disabled}
        style={{ marginBottom: 12 }}
      >
        <Radio value="none">Aucune</Radio>
        <Radio value="predefined">R\u00e8gle pr\u00e9d\u00e9finie</Radio>
        <Radio value="inline">R\u00e8gle personnalis\u00e9e (inline)</Radio>
      </Radio.Group>

      {mode === 'predefined' && (
        <Space orientation="vertical" style={{ width: '100%' }}>
          <Space style={{ width: '100%' }}>
            <Select
              value={policyId ?? undefined}
              onChange={handlePolicySelect}
              placeholder="S\u00e9lectionner une r\u00e8gle..."
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
        </Space>
      )}

      {mode === 'inline' && (
        <BusinessRulePoliciesEditor
          value={inlineJson}
          onChange={disabled ? undefined : onInlineJsonChange}
        />
      )}

      <Modal
        title={`R\u00e8gle : ${previewName}`}
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

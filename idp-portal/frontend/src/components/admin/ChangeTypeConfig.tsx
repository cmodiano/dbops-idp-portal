/**
 * ChangeTypeConfig component for configuring ServiceNow change types per environment (Story 2.2, AC #3).
 *
 * Features:
 * - Table of environments with change type selection
 * - Badge display for change type (green=pre-approved, orange=CAB)
 * - Accessibility support
 */

import React from 'react';
import { Select, Tag, Space, Typography } from 'antd';
import type { ChangeType } from '../../types/api';

const { Text } = Typography;

interface ChangeTypeConfigProps {
  value?: Record<string, ChangeType>;
  onChange?: (config: Record<string, ChangeType>) => void;
}

const ENVIRONMENTS = ['DEV', 'STAGING', 'PROD'];

const CHANGE_TYPE_OPTIONS: { value: ChangeType; label: string }[] = [
  { value: 'pre_approved', label: 'Pre-approuve' },
  { value: 'cab', label: 'CAB' },
];

const ChangeTypeBadge: React.FC<{ type: ChangeType }> = ({ type }) => {
  if (type === 'pre_approved') {
    return <Tag color="green">Pre-approuve</Tag>;
  }
  return <Tag color="orange">CAB</Tag>;
};

export const ChangeTypeConfig: React.FC<ChangeTypeConfigProps> = ({
  value = {},
  onChange,
}) => {
  const handleChange = (env: string, changeType: ChangeType) => {
    const newConfig = { ...value, [env]: changeType };
    onChange?.(newConfig);
  };

  return (
    <div role="table" aria-label="Configuration type de changement par environnement">
      <Space direction="vertical" style={{ width: '100%' }}>
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: '1fr 1fr 1fr',
            gap: '8px',
            padding: '8px',
            background: '#fafafa',
            borderRadius: '4px',
          }}
          role="row"
        >
          <Text strong role="columnheader">Environnement</Text>
          <Text strong role="columnheader">Type de changement</Text>
          <Text strong role="columnheader">Badge</Text>
        </div>

        {ENVIRONMENTS.map((env) => (
          <div
            key={env}
            style={{
              display: 'grid',
              gridTemplateColumns: '1fr 1fr 1fr',
              gap: '8px',
              padding: '8px',
              alignItems: 'center',
              borderBottom: '1px solid #f0f0f0',
            }}
            role="row"
          >
            <Text role="cell">{env}</Text>
            <Select
              value={value[env] || 'pre_approved'}
              onChange={(val) => handleChange(env, val)}
              options={CHANGE_TYPE_OPTIONS}
              style={{ width: '100%' }}
              aria-label={`Type de changement pour ${env}`}
              role="cell"
            />
            <div role="cell">
              <ChangeTypeBadge type={value[env] || 'pre_approved'} />
            </div>
          </div>
        ))}
      </Space>
    </div>
  );
};

export default ChangeTypeConfig;

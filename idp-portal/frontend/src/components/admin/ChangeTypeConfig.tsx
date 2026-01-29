/**
 * ChangeTypeConfig component for configuring ServiceNow change types per environment (Story 2.2, AC #3).
 * Story 2.8: CAB removed; only Pre-approuvé (Story 2-15: theme tokens for dark mode).
 */

import React from 'react';
import { Select, Tag, Space, Typography, theme } from 'antd';
import type { ChangeType } from '../../types/api';

const { Text } = Typography;

interface ChangeTypeConfigProps {
  value?: Record<string, ChangeType>;
  onChange?: (config: Record<string, ChangeType>) => void;
}

const ENVIRONMENTS = ['DEV', 'STAGING', 'PROD'];

const CHANGE_TYPE_OPTIONS: { value: ChangeType; label: string }[] = [
  { value: 'pre_approved', label: 'Pre-approuvé' },
];

const ChangeTypeBadge: React.FC<{ type: ChangeType }> = () => (
  <Tag color="green">Pre-approuvé</Tag>
);

export const ChangeTypeConfig: React.FC<ChangeTypeConfigProps> = ({
  value = {},
  onChange,
}) => {
  const { token } = theme.useToken();

  const handleChange = (env: string, changeType: ChangeType) => {
    const newConfig = { ...value, [env]: changeType };
    onChange?.(newConfig);
  };

  return (
    <div role="table" aria-label="Configuration type de changement par environnement">
      <Space orientation="vertical" style={{ width: '100%' }}>
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: '1fr 1fr 1fr',
            gap: '8px',
            padding: '8px',
            background: token.colorFillTertiary,
            borderRadius: token.borderRadius,
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
              borderBottom: `1px solid ${token.colorBorderSecondary}`,
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
              <ChangeTypeBadge type={(value[env] || 'pre_approved') as ChangeType} />
            </div>
          </div>
        ))}
      </Space>
    </div>
  );
};

export default ChangeTypeConfig;

/**
 * ChangeTypeConfig — Configuration changement ServiceNow par environnement (Story 2.24).
 * Pour chaque env : Switch « Changement requis » + si actif Input « Code modèle » (alphanumérique, max 50).
 */

import React from 'react';
import { Switch, Input, Space, Typography, theme } from 'antd';
import type { ChangeTypeConfigEntry } from '../../types/api';

const { Text } = Typography;

const ENVIRONMENTS = ['DEV', 'STAGING', 'PROD'];

const CODE_MAX_LENGTH = 50;
const CODE_PATTERN = /^[A-Za-z0-9]*$/;

export interface ChangeTypeConfigProps {
  value?: Record<string, ChangeTypeConfigEntry>;
  onChange?: (config: Record<string, ChangeTypeConfigEntry>) => void;
}

export const ChangeTypeConfig: React.FC<ChangeTypeConfigProps> = ({
  value = {},
  onChange,
}) => {
  const { token } = theme.useToken();

  const getEntry = (env: string): ChangeTypeConfigEntry => {
    const e = value[env];
    return e ?? { required: false };
  };

  const handleRequiredChange = (env: string, required: boolean) => {
    const entry = getEntry(env);
    const newConfig = { ...value, [env]: { ...entry, required, change_model_code: required ? (entry.change_model_code ?? '') : undefined } };
    onChange?.(newConfig);
  };

  const handleCodeChange = (env: string, code: string) => {
    if (code.length > CODE_MAX_LENGTH) return;
    if (code && !CODE_PATTERN.test(code)) return;
    const entry = getEntry(env);
    const newConfig = { ...value, [env]: { ...entry, change_model_code: code || undefined } };
    onChange?.(newConfig);
  };

  return (
    <div role="table" aria-label="Configuration type de changement par environnement">
      <Space orientation="vertical" style={{ width: '100%' }}>
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: '1fr auto 1fr',
            gap: '8px',
            padding: '8px',
            background: token.colorFillTertiary,
            borderRadius: token.borderRadius,
          }}
          role="row"
        >
          <Text strong role="columnheader">Environnement</Text>
          <Text strong role="columnheader">Changement requis</Text>
          <Text strong role="columnheader">Code modèle</Text>
        </div>

        {ENVIRONMENTS.map((env) => {
          const entry = getEntry(env);
          const required = entry.required ?? false;
          const code = entry.change_model_code ?? '';
          return (
            <div
              key={env}
              style={{
                display: 'grid',
                gridTemplateColumns: '1fr auto 1fr',
                gap: '8px',
                padding: '8px',
                alignItems: 'center',
                borderBottom: `1px solid ${token.colorBorderSecondary}`,
              }}
              role="row"
            >
              <Text role="cell">{env}</Text>
              <div role="cell">
                <Switch
                  checked={required}
                  onChange={(checked) => handleRequiredChange(env, checked)}
                  aria-label={`Changement requis pour ${env}`}
                />
              </div>
              <div role="cell">
                {required ? (
                  <Input
                    value={code}
                    onChange={(e) => handleCodeChange(env, e.target.value)}
                    placeholder="Ex: 1516B"
                    maxLength={CODE_MAX_LENGTH}
                    aria-label={`Code modèle pour ${env}`}
                  />
                ) : (
                  <Text type="secondary">—</Text>
                )}
              </div>
            </div>
          );
        })}
      </Space>
    </div>
  );
};

export default ChangeTypeConfig;

/**
 * ConditionConfig — Configuration de condition environment_in (Story 57.13).
 * Multi-select chargé depuis l'API inventaire avec saisie libre en fallback.
 */

import type { FC } from 'react';
import { Select, Typography } from 'antd';
import { useEnvironments } from '../../../hooks/useEnvironments';

const { Text } = Typography;

export interface ConditionConfigProps {
  value?: { environment_in?: string[] } | null;
  onChange: (value: { environment_in?: string[] } | null) => void;
  disabled?: boolean;
}

export const ConditionConfig: FC<ConditionConfigProps> = ({
  value,
  onChange,
  disabled = false,
}) => {
  const currentEnvs = value?.environment_in ?? [];
  const { environmentOptions, loading } = useEnvironments();

  const handleChange = (envs: string[]) => {
    if (envs.length === 0) {
      onChange(null);
    } else {
      onChange({ environment_in: envs });
    }
  };

  return (
    <div>
      <Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 4 }}>
        Filtrer par environnement (optionnel)
      </Text>
      <Select
        mode="multiple"
        size="small"
        style={{ width: '100%' }}
        value={currentEnvs}
        onChange={handleChange}
        placeholder="Tous les environnements"
        disabled={disabled}
        loading={loading}
        aria-label="Filtrer par environnement"
        options={environmentOptions}
        optionFilterProp="label"
      />
      <Text type="secondary" style={{ fontSize: 11, marginTop: 4, display: 'block' }}>
        Laisser vide pour exécuter dans tous les environnements
      </Text>
    </div>
  );
};

export default ConditionConfig;

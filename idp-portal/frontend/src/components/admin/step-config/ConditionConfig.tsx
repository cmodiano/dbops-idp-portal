/**
 * ConditionConfig — Configuration de condition environment_in (Story 57.13).
 * Multi-select libre d'environnements (l'utilisateur saisit les noms).
 */

import type { FC } from 'react';
import { Select, Typography } from 'antd';

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
        mode="tags"
        size="small"
        style={{ width: '100%' }}
        value={currentEnvs}
        onChange={handleChange}
        placeholder="ex: PROD, STAGING"
        disabled={disabled}
        aria-label="Filtrer par environnement"
        tokenSeparators={[',']}
      />
      <Text type="secondary" style={{ fontSize: 11, marginTop: 4, display: 'block' }}>
        Laisser vide pour exécuter dans tous les environnements
      </Text>
    </div>
  );
};

export default ConditionConfig;

/**
 * ChangeTypeConfig — Configuration changement ServiceNow par environnement (Story 2.24, 25.4).
 * Pour chaque env : Changement requis + Code modèle + Exécution autorisée + Plage maintenance + Approbation.
 */

import React from 'react';
import { Switch, Input, Space, Typography, theme, Skeleton, Alert } from 'antd';
import type { ChangeTypeConfigEntry } from '../../types/api';
import { useEnvironments } from '../../hooks/useEnvironments';

const { Text } = Typography;

const CODE_MAX_LENGTH = 50;
const CODE_PATTERN = /^[A-Za-z0-9]*$/;

const EMPTY_CONFIG: Record<string, ChangeTypeConfigEntry> = {};

export interface ChangeTypeConfigProps {
  value?: Record<string, ChangeTypeConfigEntry>;
  onChange?: (config: Record<string, ChangeTypeConfigEntry>) => void;
}

export const ChangeTypeConfig: React.FC<ChangeTypeConfigProps> = ({
  value = EMPTY_CONFIG,
  onChange,
}) => {
  const { token } = theme.useToken();
  const { environments, environmentOptions, loading, error } = useEnvironments();

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

  const handleChangeTypeChange = (env: string, v: string) => {
    const entry = getEntry(env);
    const newConfig = { ...value, [env]: { ...entry, change_type: v || undefined } };
    onChange?.(newConfig);
  };

  const handleTemplateIdChange = (env: string, v: string) => {
    const entry = getEntry(env);
    const newConfig = { ...value, [env]: { ...entry, template_id: v || undefined } };
    onChange?.(newConfig);
  };

  const handleAllowedChange = (env: string, allowed: boolean) => {
    const entry = getEntry(env);
    const newConfig = { ...value, [env]: { ...entry, allowed } };
    onChange?.(newConfig);
  };

  const handleRequiresMaintenanceWindowChange = (env: string, v: boolean) => {
    const entry = getEntry(env);
    const newConfig = { ...value, [env]: { ...entry, requires_maintenance_window: v } };
    onChange?.(newConfig);
  };

  const handleRequiresApprovalChange = (env: string, v: boolean) => {
    const entry = getEntry(env);
    const newConfig = { ...value, [env]: { ...entry, requires_approval: v } };
    onChange?.(newConfig);
  };

  if (loading) {
    return <Skeleton active paragraph={{ rows: 3 }} />;
  }

  // If error, still render the grid but show warning at top
  const errorAlert = error ? (
    <Alert
      message="Erreur de chargement des environnements depuis l'inventaire"
      description="Utilisation des environnements par défaut (dev, staging, prod). Rechargez la page pour réessayer."
      type="warning"
      showIcon
      style={{ marginBottom: 16 }}
    />
  ) : null;

  const getLabel = (env: string): string =>
    environmentOptions.find((opt) => opt.value === env)?.label || env.toUpperCase();

  return (
    <div>
      {errorAlert}
      <div role="table" aria-label="Configuration type de changement par environnement">
        <Space orientation="vertical" style={{ width: '100%' }}>
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: '1fr auto auto auto auto 1fr 1fr 1fr',
            gap: '8px',
            padding: '8px',
            background: token.colorFillTertiary,
            borderRadius: token.borderRadius,
          }}
          role="row"
        >
          <Text strong role="columnheader">Environnement</Text>
          <Text strong role="columnheader">Autorisé</Text>
          <Text strong role="columnheader">Changement requis</Text>
          <Text strong role="columnheader">Plage maintenance</Text>
          <Text strong role="columnheader">Approbation</Text>
          <Text strong role="columnheader">Code modèle</Text>
          <Text strong role="columnheader">Change type</Text>
          <Text strong role="columnheader">Template ID</Text>
        </div>

        {environments.map((env) => {
          const entry = getEntry(env);
          const required = entry.required ?? false;
          const code = entry.change_model_code ?? '';
          const allowed = entry.allowed ?? true;
          const requiresMaintenanceWindow = entry.requires_maintenance_window ?? false;
          const requiresApproval = entry.requires_approval ?? false;
          const changeType = entry.change_type ?? '';
          const templateId = entry.template_id ?? '';
          return (
            <div
              key={env}
              style={{
                display: 'grid',
                gridTemplateColumns: '1fr auto auto auto auto 1fr 1fr 1fr',
                gap: '8px',
                padding: '8px',
                alignItems: 'center',
                borderBottom: `1px solid ${token.colorBorderSecondary}`,
              }}
              role="row"
            >
              <Text role="cell">{getLabel(env)}</Text>
              <div role="cell">
                <Switch
                  checked={allowed}
                  onChange={(checked) => handleAllowedChange(env, checked)}
                  aria-label={`Exécution autorisée pour ${env}`}
                />
              </div>
              <div role="cell">
                <Switch
                  checked={required}
                  onChange={(checked) => handleRequiredChange(env, checked)}
                  aria-label={`Changement requis pour ${env}`}
                />
              </div>
              <div role="cell">
                <Switch
                  checked={requiresMaintenanceWindow}
                  onChange={(checked) => handleRequiresMaintenanceWindowChange(env, checked)}
                  aria-label={`Plage de maintenance requise pour ${env}`}
                />
              </div>
              <div role="cell">
                <Switch
                  checked={requiresApproval}
                  onChange={(checked) => handleRequiresApprovalChange(env, checked)}
                  aria-label={`Approbation requise pour ${env}`}
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
              <div role="cell">
                <Input
                  value={changeType}
                  onChange={(e) => handleChangeTypeChange(env, e.target.value)}
                  placeholder="Ex: normal"
                  aria-label={`Change type pour ${env}`}
                />
              </div>
              <div role="cell">
                <Input
                  value={templateId}
                  onChange={(e) => handleTemplateIdChange(env, e.target.value)}
                  placeholder="Ex: CHG_TPL_001"
                  aria-label={`Template ID pour ${env}`}
                />
              </div>
            </div>
          );
        })}
        </Space>
      </div>
    </div>
  );
};

export default ChangeTypeConfig;

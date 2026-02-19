/**
 * ChangeTypeConfig — Configuration par environnement, séparée en deux blocs (Story 31.4).
 *
 * Bloc 1 — Gates : Autorisé, Plage maintenance, Approbation (conditions d'exécution)
 * Bloc 2 — Changement ServiceNow : Changement requis, Modèle / Template ID (unifié), Change type
 *
 * Le champ « Modèle / Template ID » fusionne l'ancien Code modèle et Template ID.
 * Lecture : template_id ?? change_model_code ?? ''
 * Écriture : les deux champs sont écrits simultanément pour rétrocompatibilité.
 */

import React from 'react';
import { Switch, Input, Space, Typography, theme, Skeleton, Alert, Divider } from 'antd';
import type { ChangeTypeConfigEntry } from '../../types/api';
import { useEnvironments } from '../../hooks/useEnvironments';

const { Text } = Typography;

const CODE_MAX_LENGTH = 50;
const CODE_PATTERN = /^[A-Za-z0-9_-]*$/;

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

  const handleRequiredChange = (env: string, required: boolean) => {
    const entry = getEntry(env);
    const modelValue = required ? (entry.template_id ?? entry.change_model_code ?? '') : undefined;
    const newConfig = {
      ...value,
      [env]: { ...entry, required, change_model_code: modelValue, template_id: modelValue },
    };
    onChange?.(newConfig);
  };

  const handleModelTemplateChange = (env: string, v: string) => {
    if (v.length > CODE_MAX_LENGTH) return;
    if (v && !CODE_PATTERN.test(v)) return;
    const entry = getEntry(env);
    const newConfig = {
      ...value,
      [env]: { ...entry, change_model_code: v || undefined, template_id: v || undefined },
    };
    onChange?.(newConfig);
  };

  const handleChangeTypeChange = (env: string, v: string) => {
    const entry = getEntry(env);
    const newConfig = { ...value, [env]: { ...entry, change_type: v || undefined } };
    onChange?.(newConfig);
  };

  if (loading) {
    return <Skeleton active paragraph={{ rows: 3 }} />;
  }

  const errorAlert = error ? (
    <Alert
      title="Erreur de chargement des environnements depuis l'inventaire"
      description="Utilisation des environnements par défaut (dev, staging, prod). Rechargez la page pour réessayer."
      type="warning"
      showIcon
      style={{ marginBottom: 16 }}
    />
  ) : null;

  const getLabel = (env: string): string =>
    environmentOptions.find((opt) => opt.value === env)?.label || env.toUpperCase();

  const headerStyle: React.CSSProperties = {
    padding: '8px',
    background: token.colorFillTertiary,
    borderRadius: token.borderRadius,
  };

  const rowStyle: React.CSSProperties = {
    padding: '8px',
    alignItems: 'center',
    borderBottom: `1px solid ${token.colorBorderSecondary}`,
  };

  return (
    <div>
      {errorAlert}
      <div role="table" aria-label="Configuration type de changement par environnement">
        <Space orientation="vertical" style={{ width: '100%' }}>

          {/* Bloc 1 — Gates */}
          <div role="group" aria-label="Gates — Conditions d'exécution par environnement">
            <Text strong style={{ fontSize: 14 }}>Gates — Conditions d&apos;exécution par environnement</Text>
            <div
              style={{ display: 'grid', gridTemplateColumns: '1fr auto auto auto', gap: '8px', ...headerStyle, marginTop: 8 }}
              role="row"
            >
              <Text strong role="columnheader">Environnement</Text>
              <Text strong role="columnheader">Autorisé</Text>
              <Text strong role="columnheader">Plage maintenance</Text>
              <Text strong role="columnheader">Approbation</Text>
            </div>
            {environments.map((env) => {
              const entry = getEntry(env);
              const allowed = entry.allowed ?? true;
              const requiresMaintenanceWindow = entry.requires_maintenance_window ?? false;
              const requiresApproval = entry.requires_approval ?? false;
              return (
                <div
                  key={env}
                  style={{ display: 'grid', gridTemplateColumns: '1fr auto auto auto', gap: '8px', ...rowStyle }}
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
                </div>
              );
            })}
          </div>

          <Divider style={{ margin: '12px 0' }} />

          {/* Bloc 2 — Changement ServiceNow */}
          <div role="group" aria-label="Changement ServiceNow par environnement">
            <Text strong style={{ fontSize: 14 }}>Changement ServiceNow par environnement</Text>
            <div
              style={{ display: 'grid', gridTemplateColumns: '1fr auto 1fr 1fr', gap: '8px', ...headerStyle, marginTop: 8 }}
              role="row"
            >
              <Text strong role="columnheader">Environnement</Text>
              <Text strong role="columnheader">Changement requis</Text>
              <Text strong role="columnheader">Modèle / Template ID</Text>
              <Text strong role="columnheader">Change type</Text>
            </div>
            {environments.map((env) => {
              const entry = getEntry(env);
              const required = entry.required ?? false;
              const modelTemplateValue = entry.template_id ?? entry.change_model_code ?? '';
              const changeType = entry.change_type ?? '';
              return (
                <div
                  key={env}
                  style={{ display: 'grid', gridTemplateColumns: '1fr auto 1fr 1fr', gap: '8px', ...rowStyle }}
                  role="row"
                >
                  <Text role="cell">{getLabel(env)}</Text>
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
                        value={modelTemplateValue}
                        onChange={(e) => handleModelTemplateChange(env, e.target.value)}
                        placeholder="Ex: CHG_TPL_001"
                        maxLength={CODE_MAX_LENGTH}
                        aria-label={`Modèle / Template ID pour ${env}`}
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
                </div>
              );
            })}
          </div>

        </Space>
      </div>
    </div>
  );
};

export default ChangeTypeConfig;

/**
 * Story 31.8: Section de configuration des notifications pour les actions.
 * Affiche 4 blocs activables : Email, Teams, Page individuel, Page DBA.
 * Chaque bloc a un toggle on/off + conditions (on_failure, on_success, always).
 */

import type { FC, CSSProperties } from 'react';
import { Switch, Input, Checkbox, Typography, Space, theme, Divider, Alert } from 'antd';
import type { NotificationConfig, NotificationChannel } from '../../types/api/catalog';

const { Text } = Typography;

const CHANNEL_LABELS: Record<string, string> = {
  email: 'Email',
  teams: 'Teams (webhook)',
  page_dba: 'Page DBA on-call',
};

const CONDITION_LABELS: Record<string, string> = {
  on_failure: 'En cas d\'échec',
  on_success: 'En cas de succès',
  always: 'Toujours',
  on_approval_required: 'Approbation requise',
};

const DEFAULT_CHANNELS: NotificationChannel[] = [
  { type: 'email', enabled: false, conditions: [], recipient: 'requester' },
  { type: 'teams', enabled: false, conditions: [], webhook_url_ref: '' },
  { type: 'page_dba', enabled: false, conditions: [], api_url: '' },
];

export interface NotificationConfigSectionProps {
  value?: NotificationConfig | null;
  onChange?: (config: NotificationConfig) => void;
}

export const NotificationConfigSection: FC<NotificationConfigSectionProps> = ({
  value,
  onChange,
}) => {
  const { token } = theme.useToken();

  const config: NotificationConfig = value ?? {
    channels: [...DEFAULT_CHANNELS],
    page_individual_enabled: false,
  };

  const channels = config.channels.length > 0
    ? config.channels
    : [...DEFAULT_CHANNELS];

  const getChannel = (type: string): NotificationChannel => {
    return channels.find((ch) => ch.type === type) ?? DEFAULT_CHANNELS.find((ch) => ch.type === type)!;
  };

  const updateChannel = (type: string, updates: Partial<NotificationChannel>) => {
    const newChannels = channels.map((ch) =>
      ch.type === type ? { ...ch, ...updates } : ch,
    );
    // Ensure all default channels exist
    for (const def of DEFAULT_CHANNELS) {
      if (!newChannels.find((ch) => ch.type === def.type)) {
        newChannels.push({ ...def });
      }
    }
    onChange?.({ ...config, channels: newChannels });
  };

  const handlePageIndividualChange = (checked: boolean) => {
    onChange?.({ ...config, page_individual_enabled: checked });
  };

  const handleConditionsChange = (type: string, selected: string[]) => {
    updateChannel(type, { conditions: selected as NotificationChannel['conditions'] });
  };

  const headerStyle: CSSProperties = {
    padding: '4px 8px',
    background: token.colorFillQuaternary,
    borderRadius: token.borderRadius,
    fontWeight: 500,
  };

  const rowStyle: CSSProperties = {
    padding: '8px',
    borderBottom: `1px solid ${token.colorBorderSecondary}`,
    alignItems: 'center',
  };

  const conditionOptions = Object.entries(CONDITION_LABELS).map(([value, label]) => ({
    label,
    value,
  }));

  return (
    <Space orientation="vertical" style={{ width: '100%' }} size="small">
      {/* Email */}
      <div style={headerStyle}>
        <Space>
          <Switch
            size="small"
            checked={getChannel('email').enabled}
            onChange={(checked) => updateChannel('email', { enabled: checked })}
            aria-label="Activer les notifications email"
          />
          <Text strong>{CHANNEL_LABELS.email}</Text>
        </Space>
      </div>
      {getChannel('email').enabled && (
        <div style={rowStyle}>
          <Space orientation="vertical" style={{ width: '100%' }} size="small">
            <div>
              <Text type="secondary">Destinataire :</Text>
              <Input
                size="small"
                value={getChannel('email').recipient ?? 'requester'}
                onChange={(e) => updateChannel('email', { recipient: e.target.value })}
                placeholder="requester ou adresse email"
                style={{ marginLeft: 8, width: 250 }}
                aria-label="Destinataire email"
              />
            </div>
            <div>
              <Text type="secondary">Conditions :</Text>
              <Checkbox.Group
                options={conditionOptions}
                value={getChannel('email').conditions}
                onChange={(checked) => handleConditionsChange('email', checked as string[])}
                style={{ marginLeft: 8 }}
              />
            </div>
          </Space>
        </div>
      )}

      {/* Teams */}
      <div style={headerStyle}>
        <Space>
          <Switch
            size="small"
            checked={getChannel('teams').enabled}
            onChange={(checked) => updateChannel('teams', { enabled: checked })}
            aria-label="Activer les notifications Teams"
          />
          <Text strong>{CHANNEL_LABELS.teams}</Text>
        </Space>
      </div>
      {getChannel('teams').enabled && (
        <div style={rowStyle}>
          <Space orientation="vertical" style={{ width: '100%' }} size="small">
            <div>
              <Text type="secondary">Webhook URL :</Text>
              <Input
                size="small"
                value={getChannel('teams').webhook_url_ref ?? ''}
                onChange={(e) => updateChannel('teams', { webhook_url_ref: e.target.value })}
                placeholder="https://webhook.office.com/... ou vault:secret/..."
                style={{ marginLeft: 8, width: 400 }}
                aria-label="URL webhook Teams"
              />
            </div>
            <div>
              <Text type="secondary">Conditions :</Text>
              <Checkbox.Group
                options={conditionOptions}
                value={getChannel('teams').conditions}
                onChange={(checked) => handleConditionsChange('teams', checked as string[])}
                style={{ marginLeft: 8 }}
              />
            </div>
          </Space>
        </div>
      )}

      <Divider style={{ margin: '8px 0' }} />

      {/* Page individuel */}
      <div style={headerStyle}>
        <Space>
          <Switch
            size="small"
            checked={config.page_individual_enabled}
            onChange={handlePageIndividualChange}
            aria-label="Activer le page individuel"
          />
          <Text strong>Page individuel</Text>
          <Text type="secondary" style={{ fontSize: 12 }}>
            (option disponible à l&apos;exécution — production + critique uniquement)
          </Text>
        </Space>
      </div>

      {/* Page DBA */}
      <div style={headerStyle}>
        <Space>
          <Switch
            size="small"
            checked={getChannel('page_dba').enabled}
            onChange={(checked) => updateChannel('page_dba', { enabled: checked })}
            aria-label="Activer le page DBA"
          />
          <Text strong>{CHANNEL_LABELS.page_dba}</Text>
          <Text type="secondary" style={{ fontSize: 12 }}>
            (production + critique uniquement)
          </Text>
        </Space>
      </div>
      {getChannel('page_dba').enabled && (
        <div style={rowStyle}>
          <Space orientation="vertical" style={{ width: '100%' }} size="small">
            <div>
              <Text type="secondary">URL API (optionnel) :</Text>
              <Input
                size="small"
                value={getChannel('page_dba').api_url ?? ''}
                onChange={(e) => updateChannel('page_dba', { api_url: e.target.value })}
                placeholder="Si vide, utilise la configuration serveur"
                style={{ marginLeft: 8, width: 400 }}
                aria-label="URL API page DBA"
              />
            </div>
            <div>
              <Text type="secondary">Conditions :</Text>
              <Checkbox.Group
                options={conditionOptions}
                value={getChannel('page_dba').conditions}
                onChange={(checked) => handleConditionsChange('page_dba', checked as string[])}
                style={{ marginLeft: 8 }}
              />
            </div>
          </Space>
        </div>
      )}

      {(getChannel('page_dba').enabled || config.page_individual_enabled) && (
        <Alert
          type="info"
          title="Les pages (individuel et DBA) ne sont envoyés que si l'environnement est « prod » et le niveau d'impact est « critical »."
          style={{ marginTop: 8 }}
          showIcon
        />
      )}
    </Space>
  );
};

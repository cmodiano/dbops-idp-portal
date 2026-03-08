/**
 * DriftBadge - Visual badge for IaC Git synchronization status (Story 64.13).
 *
 * Displays three states:
 * - "Synchronisé": green tag (last_synced_at != null && updated_at <= last_synced_at)
 * - "Divergé": orange tag with tooltip (last_synced_at != null && updated_at > last_synced_at)
 * - "UI only": blue tag (last_synced_at == null, never synced from Git)
 */

import { Tag, Tooltip, theme } from 'antd';
import { CheckCircleOutlined, WarningOutlined, CloudUploadOutlined } from '@ant-design/icons';
import { getDriftStatus } from './driftUtils';

interface DriftBadgeProps {
  last_synced_at: string | null | undefined;
  updated_at: string | null | undefined;
}

export function DriftBadge({ last_synced_at, updated_at }: DriftBadgeProps) {
  const { token } = theme.useToken();
  const status = getDriftStatus(last_synced_at, updated_at);

  if (status === 'synced') {
    return (
      <Tag
        icon={<CheckCircleOutlined />}
        aria-label="Sync Git: Synchronisé"
        color={token.colorSuccess}
      >
        Synchronisé
      </Tag>
    );
  }

  if (status === 'diverged') {
    const tooltipText = last_synced_at
      ? `Dernier sync : ${new Date(last_synced_at).toLocaleString('fr-FR')}`
      : '';
    return (
      <Tooltip title={tooltipText}>
        <Tag
          icon={<WarningOutlined />}
          aria-label="Sync Git: Divergé"
          color={token.colorWarning}
        >
          Divergé
        </Tag>
      </Tooltip>
    );
  }

  // ui-only
  return (
    <Tag
      icon={<CloudUploadOutlined />}
      aria-label="Sync Git: UI only"
      color={token.colorInfo}
    >
      UI only
    </Tag>
  );
}

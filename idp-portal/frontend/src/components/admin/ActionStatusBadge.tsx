/**
 * ActionStatusBadge - Visual badge for action lifecycle status (Story 2.4, AC #2).
 * Story 2-15: uses theme token for draft so badge is visible in dark mode (AC #4, #5).
 *
 * Displays action status with appropriate color coding:
 * - draft: theme secondary text (works in light/dark)
 * - published: vert lisible (fond saturé, texte blanc)
 * - disabled: red
 */

import { Tag, theme } from 'antd';
import { EditOutlined, CheckCircleOutlined, StopOutlined } from '@ant-design/icons';
import type { ActionStatus } from '../../types/api';

/** Vert Publiée: fond saturé pour bonne lisibilité (évite le badge trop clair) */
const PUBLISHED_BG = '#006b3e';
const PUBLISHED_TEXT = '#fff';

interface ActionStatusBadgeProps {
  status: ActionStatus;
}

export function ActionStatusBadge({ status }: ActionStatusBadgeProps) {
  const { token } = theme.useToken();

  const draftConfig = {
    label: 'Brouillon',
    icon: <EditOutlined />,
  };
  const publishedConfig = {
    label: 'Publiée',
    icon: <CheckCircleOutlined />,
  };
  const disabledConfig = {
    color: token.colorError,
    label: 'Désactivée',
    icon: <StopOutlined />,
  };

  const config =
    status === 'draft' ? draftConfig
    : status === 'published' ? publishedConfig
    : disabledConfig;

  if (status === 'draft') {
    return (
      <Tag
        icon={config.icon}
        aria-label={`Statut: ${config.label}`}
        style={{ color: token.colorTextSecondary, borderColor: token.colorBorder }}
      >
        {config.label}
      </Tag>
    );
  }

  if (status === 'published') {
    return (
      <Tag
        icon={config.icon}
        aria-label={`Statut: ${config.label}`}
        style={{
          background: PUBLISHED_BG,
          color: PUBLISHED_TEXT,
          borderColor: PUBLISHED_BG,
        }}
      >
        {config.label}
      </Tag>
    );
  }

  return (
    <Tag
      color={disabledConfig.color}
      icon={disabledConfig.icon}
      aria-label={`Statut: ${disabledConfig.label}`}
    >
      {disabledConfig.label}
    </Tag>
  );
}

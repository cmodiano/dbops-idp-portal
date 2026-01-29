/**
 * ActionStatusBadge - Visual badge for action lifecycle status (Story 2.4, AC #2).
 * Story 2-15: uses theme token for draft so badge is visible in dark mode (AC #4, #5).
 *
 * Displays action status with appropriate color coding:
 * - draft: theme secondary text (works in light/dark)
 * - published: green
 * - disabled: red
 */

import { Tag, theme } from 'antd';
import { EditOutlined, CheckCircleOutlined, StopOutlined } from '@ant-design/icons';
import type { ActionStatus } from '../../types/api';

interface ActionStatusBadgeProps {
  status: ActionStatus;
}

export function ActionStatusBadge({ status }: ActionStatusBadgeProps) {
  const { token } = theme.useToken();

  const draftConfig = {
    color: token.colorTextSecondary,
    label: 'Brouillon',
    icon: <EditOutlined />,
  };
  const publishedConfig = {
    color: token.colorSuccess,
    label: 'Publiee',
    icon: <CheckCircleOutlined />,
  };
  const disabledConfig = {
    color: token.colorError,
    label: 'Desactivee',
    icon: <StopOutlined />,
  };

  const config =
    status === 'draft' ? draftConfig
    : status === 'published' ? publishedConfig
    : disabledConfig;

  return (
    <Tag
      color={status === 'draft' ? undefined : config.color}
      icon={config.icon}
      aria-label={`Statut: ${config.label}`}
      style={status === 'draft' ? { color: token.colorTextSecondary, borderColor: token.colorBorder } : undefined}
    >
      {config.label}
    </Tag>
  );
}

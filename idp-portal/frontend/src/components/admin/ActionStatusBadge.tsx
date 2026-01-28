/**
 * ActionStatusBadge - Visual badge for action lifecycle status (Story 2.4, AC #2).
 *
 * Displays action status with appropriate color coding:
 * - draft: gray
 * - published: green
 * - disabled: red
 */

import { Tag } from 'antd';
import { EditOutlined, CheckCircleOutlined, StopOutlined } from '@ant-design/icons';
import type { ActionStatus } from '../../types/api';

interface ActionStatusBadgeProps {
  status: ActionStatus;
}

const STATUS_CONFIG: Record<ActionStatus, { color: string; label: string; icon: React.ReactNode }> = {
  draft: {
    color: '#9CA3AF',
    label: 'Brouillon',
    icon: <EditOutlined />,
  },
  published: {
    color: '#10B981',
    label: 'Publiee',
    icon: <CheckCircleOutlined />,
  },
  disabled: {
    color: '#EF4444',
    label: 'Desactivee',
    icon: <StopOutlined />,
  },
};

export function ActionStatusBadge({ status }: ActionStatusBadgeProps) {
  const config = STATUS_CONFIG[status];

  return (
    <Tag
      color={config.color}
      icon={config.icon}
      aria-label={`Statut: ${config.label}`}
    >
      {config.label}
    </Tag>
  );
}

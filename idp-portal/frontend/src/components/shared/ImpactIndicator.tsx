/**
 * ImpactIndicator - Triple coding indicator for action impact level (Story 2.5, AC #2).
 *
 * Displays impact level with:
 * - Color coding (green/yellow/orange/red)
 * - Icon (visual indicator)
 * - Text label (screen reader and visual)
 *
 * WCAG 2.1 AA compliant with aria-label for accessibility.
 */

import { Tag } from 'antd';
import {
  CheckCircleOutlined,
  ExclamationCircleOutlined,
  WarningOutlined,
  CloseCircleOutlined,
} from '@ant-design/icons';
import type { ImpactLevel } from '../../types/api';
import { STYLE_TOKENS } from '../../theme/styleTokens';

export interface ImpactIndicatorProps {
  level: ImpactLevel;
  size?: 'small' | 'default';
}

/** Exported for ActionCard aria-label (UX spec: "[nom], impact [niveau]"). */
export const IMPACT_LABELS: Record<ImpactLevel, string> = {
  low: 'Faible',
  medium: 'Moyen',
  high: 'Eleve',
  critical: 'Critique',
};

interface ImpactConfig {
  color: string;
  label: string;
  icon: React.ReactNode;
}

const IMPACT_CONFIG: Record<ImpactLevel, ImpactConfig> = {
  low: {
    color: STYLE_TOKENS.impactColor.low,
    label: IMPACT_LABELS.low,
    icon: <CheckCircleOutlined />,
  },
  medium: {
    color: STYLE_TOKENS.impactColor.medium,
    label: IMPACT_LABELS.medium,
    icon: <ExclamationCircleOutlined />,
  },
  high: {
    color: STYLE_TOKENS.impactColor.high,
    label: IMPACT_LABELS.high,
    icon: <WarningOutlined />,
  },
  critical: {
    color: STYLE_TOKENS.impactColor.critical,
    label: IMPACT_LABELS.critical,
    icon: <CloseCircleOutlined />,
  },
};

export function ImpactIndicator({ level, size = 'default' }: ImpactIndicatorProps) {
  const config = IMPACT_CONFIG[level];

  return (
    <span aria-label={`Impact: ${config.label}`} role="status">
      <Tag
        color={config.color}
        icon={config.icon}
        style={size === 'small' ? { fontSize: 12, padding: '0 6px' } : undefined}
      >
        {config.label}
      </Tag>
    </span>
  );
}

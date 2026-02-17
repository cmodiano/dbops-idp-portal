/**
 * StatCard - Dashboard statistic card (Story 5.1, Task 3.1).
 *
 * Displays a single metric with label, value, optional icon, and status variant.
 * Variants: default, success, error, inProgress.
 * Default variant uses theme tokens so "Exécutions aujourd'hui" is readable in dark mode.
 */

import { Card, Skeleton, Typography, theme } from 'antd';
import { ReactNode } from 'react';

const { Text, Title } = Typography;

export type StatCardVariant = 'default' | 'success' | 'error' | 'inProgress';

const VARIANT_STYLES: Record<StatCardVariant, { borderColor: string; valueColor: string } | null> = {
  default: null, // use theme tokens
  success: { borderColor: '#10B981', valueColor: '#10B981' },
  error: { borderColor: '#EF4444', valueColor: '#EF4444' },
  inProgress: { borderColor: '#3B82F6', valueColor: '#3B82F6' },
};

export interface StatCardProps {
  /** Metric label displayed above the value. */
  label: string;
  /** Numeric or string value to display prominently. */
  value: number | string;
  /** Optional icon displayed next to the value. */
  icon?: ReactNode;
  /** Visual variant for the card. */
  variant?: StatCardVariant;
  /** Whether the card is in loading state (shows skeleton). */
  loading?: boolean;
  /** Suffix to append after the value (e.g., '%'). */
  suffix?: string;
}

export function StatCard({
  label,
  value,
  icon,
  variant = 'default',
  loading = false,
  suffix,
}: StatCardProps) {
  const { token } = theme.useToken();
  const resolved =
    VARIANT_STYLES[variant] ?? {
      borderColor: token.colorBorder,
      valueColor: token.colorText,
    };
  const styles = resolved;

  if (loading) {
    return (
      <Card
        style={{
          borderLeft: `4px solid ${styles.borderColor}`,
          height: '100%',
        }}
        styles={{ body: { padding: 16 } }}
      >
        <Skeleton active title={{ width: '60%' }} paragraph={{ rows: 1, width: '40%' }} />
      </Card>
    );
  }

  return (
    <Card
      style={{
        borderLeft: `4px solid ${styles.borderColor}`,
        height: '100%',
      }}
      styles={{ body: { padding: 16 } }}
    >
      <Text type="secondary" style={{ fontSize: 13, marginBottom: 4, display: 'block' }}>
        {label}
      </Text>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        {icon && <span style={{ color: styles.valueColor, fontSize: 24 }}>{icon}</span>}
        <Title
          level={3}
          style={{
            margin: 0,
            color: styles.valueColor,
            fontWeight: 600,
          }}
        >
          {value}{suffix}
        </Title>
      </div>
    </Card>
  );
}

export default StatCard;

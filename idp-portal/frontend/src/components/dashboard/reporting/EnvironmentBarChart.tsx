/**
 * EnvironmentBarChart - Horizontal bar chart showing executions by environment.
 * Story 8.3, AC4.
 *
 * Uses recharts BarChart with horizontal layout (layout="vertical").
 * Environment colors: dev (green), staging (orange), prod (red).
 */

import { Card, Empty, Skeleton } from 'antd';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from 'recharts';
import type { EnvironmentStats } from '../../../types/api';

export interface EnvironmentBarChartProps {
  /** Environment stats data. */
  data: EnvironmentStats[];
  /** Whether the chart is loading. */
  loading?: boolean;
}

/** Environment color palette (Story 8.3 Dev Notes). */
const ENVIRONMENT_COLORS: Record<string, string> = {
  dev: '#10B981',     // vert
  staging: '#F59E0B', // orange
  prod: '#EF4444',    // rouge
};

/**
 * Get hex color for an environment (fallback to gray).
 *
 * NOTE: This is intentionally different from utils/environmentHelpers getEnvironmentColor(),
 * which returns BadgeProps['status'] for Ant Design badges. This function returns hex codes
 * for Recharts visualization. Story 21.5 does not consolidate this because the return types
 * and use cases differ.
 */
function getEnvironmentColor(env: string): string {
  return ENVIRONMENT_COLORS[env.toLowerCase()] ?? '#6B7280';
}

/** Chart sizing constants. */
const MIN_CHART_HEIGHT = 150;
const BAR_HEIGHT_PER_ITEM = 50;

/** Custom tooltip content with count and success rate. */
function CustomTooltip({ active, payload, label }: { active?: boolean; payload?: Array<{ payload: EnvironmentStats }>; label?: string }) {
  if (!active || !payload?.length) return null;
  const data = payload[0]?.payload as EnvironmentStats;
  return (
    <div style={{
      background: 'var(--color-bg-elevated, #fff)',
      padding: '8px 12px',
      border: '1px solid var(--color-border-secondary, #d9d9d9)',
      borderRadius: 4,
      fontSize: 13,
    }}>
      <div style={{ fontWeight: 600, marginBottom: 4 }}>{label}</div>
      <div>Exécutions: {data.count}</div>
      {data.success_rate !== null && (
        <div>Taux de succès: {data.success_rate.toFixed(1)}%</div>
      )}
    </div>
  );
}

export function EnvironmentBarChart({ data, loading = false }: EnvironmentBarChartProps) {
  if (loading) {
    return (
      <Card title={<span style={{ fontSize: 15, fontWeight: 600 }}>Répartition par environnement</span>} size="small">
        <Skeleton active paragraph={{ rows: 3 }} />
      </Card>
    );
  }

  if (!data.length) {
    return (
      <Card title={<span style={{ fontSize: 15, fontWeight: 600 }}>Répartition par environnement</span>} size="small">
        <Empty description="Aucune exécution sur la période" image={Empty.PRESENTED_IMAGE_SIMPLE} />
      </Card>
    );
  }

  return (
    <Card title={<span style={{ fontSize: 15, fontWeight: 600 }}>Répartition par environnement</span>} size="small">
      <ResponsiveContainer width="100%" height={Math.max(MIN_CHART_HEIGHT, data.length * BAR_HEIGHT_PER_ITEM)}>
        <BarChart
          data={data}
          layout="vertical"
          margin={{ top: 8, right: 24, left: 0, bottom: 8 }}
          aria-label="Graphique des exécutions par environnement"
        >
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(0,0,0,0.06)" horizontal={false} />
          <XAxis
            type="number"
            tick={{ fontSize: 13 }}
            tickLine={false}
            axisLine={{ stroke: 'rgba(0,0,0,0.06)' }}
            allowDecimals={false}
          />
          <YAxis
            type="category"
            dataKey="environment"
            tick={{ fontSize: 13 }}
            tickLine={false}
            axisLine={false}
            width={80}
          />
          <Tooltip content={<CustomTooltip />} />
          <Bar dataKey="count" name="Executions" radius={[0, 4, 4, 0]}>
            {data.map((entry, index) => (
              <Cell key={`cell-${index}`} fill={getEnvironmentColor(entry.environment)} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </Card>
  );
}

export default EnvironmentBarChart;

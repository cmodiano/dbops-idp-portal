/**
 * ProfileBarChart - Horizontal bar chart showing executions by user profile.
 * Story 8.2, AC1, Task 8.
 *
 * Uses recharts BarChart with horizontal layout (layout="vertical").
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
import type { ProfileExecutions } from '../../../types/api';

export interface ProfileBarChartProps {
  /** Executions data by profile. */
  data: ProfileExecutions[];
  /** Whether the chart is loading. */
  loading?: boolean;
}

/** Profile color palette. */
const PROFILE_COLORS: string[] = [
  '#3B82F6', // blue
  '#10B981', // green
  '#8B5CF6', // purple
  '#F59E0B', // amber
  '#EF4444', // red
  '#06B6D4', // cyan
  '#EC4899', // pink
  '#6B7280', // gray
];

/** Get color for a profile (cycle through palette). */
function getProfileColor(index: number): string {
  return PROFILE_COLORS[index % PROFILE_COLORS.length];
}

/** Chart sizing constants. */
const MIN_CHART_HEIGHT = 200;
const BAR_HEIGHT_PER_ITEM = 50;

export function ProfileBarChart({ data, loading = false }: ProfileBarChartProps) {
  if (loading) {
    return (
      <Card title={<span style={{ fontSize: 15, fontWeight: 600 }}>Exécutions par profil</span>} size="small">
        <Skeleton active paragraph={{ rows: 4 }} />
      </Card>
    );
  }

  if (!data.length) {
    return (
      <Card title={<span style={{ fontSize: 15, fontWeight: 600 }}>Exécutions par profil</span>} size="small">
        <Empty description="Aucune exécution" image={Empty.PRESENTED_IMAGE_SIMPLE} />
      </Card>
    );
  }

  return (
    <Card title={<span style={{ fontSize: 15, fontWeight: 600 }}>Exécutions par profil</span>} size="small">
      <ResponsiveContainer width="100%" height={Math.max(MIN_CHART_HEIGHT, data.length * BAR_HEIGHT_PER_ITEM)}>
        <BarChart
          data={data}
          layout="vertical"
          margin={{ top: 8, right: 24, left: 0, bottom: 8 }}
          aria-label="Graphique des exécutions par profil utilisateur"
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
            dataKey="profile"
            tick={{ fontSize: 13 }}
            tickLine={false}
            axisLine={false}
            width={100}
          />
          <Tooltip
            formatter={(value: number | undefined) => [value ?? 0, 'Exécutions']}
            contentStyle={{ fontSize: 13 }}
            labelStyle={{ fontWeight: 600 }}
          />
          <Bar dataKey="count" name="Executions" radius={[0, 4, 4, 0]}>
            {data.map((_, index) => (
              <Cell key={`cell-${index}`} fill={getProfileColor(index)} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </Card>
  );
}

export default ProfileBarChart;

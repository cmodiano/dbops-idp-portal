/**
 * AdoptionByProfileChart - Vertical bar chart showing executions by user profile.
 * Story 60.4, AC: 1, 3, 4, 5, 8.
 *
 * Uses recharts BarChart with default vertical layout.
 * Always displayed regardless of RBAC (data from stats-adoption, accessible to all authenticated users).
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
} from 'recharts';
import type { StatsAdoptionByProfile } from '../../../types/api';

export interface AdoptionByProfileChartProps {
  data: StatsAdoptionByProfile[];
  loading?: boolean;
}

const CHART_HEIGHT = 280;

function CustomTooltip({ active, payload, label }: { active?: boolean; payload?: Array<{ payload: StatsAdoptionByProfile }>; label?: string }) {
  if (!active || !payload?.length) return null;
  const data = payload[0]?.payload as StatsAdoptionByProfile;
  return (
    <div style={{ fontSize: 13 }}>
      <div style={{ fontWeight: 600, marginBottom: 4 }}>{label}</div>
      <div>Exécutions : {data.count}</div>
    </div>
  );
}

export function AdoptionByProfileChart({ data, loading = false }: AdoptionByProfileChartProps) {
  if (loading) {
    return (
      <Card title={<span style={{ fontSize: 15, fontWeight: 600 }}>Adoption par profil</span>} size="small">
        <Skeleton active paragraph={{ rows: 4 }} />
      </Card>
    );
  }

  if (!data.length) {
    return (
      <Card title={<span style={{ fontSize: 15, fontWeight: 600 }}>Adoption par profil</span>} size="small">
        <Empty description="Aucune donnée d'adoption" image={Empty.PRESENTED_IMAGE_SIMPLE} />
      </Card>
    );
  }

  return (
    <Card title={<span style={{ fontSize: 15, fontWeight: 600 }}>Adoption par profil</span>} size="small">
      <ResponsiveContainer width="100%" height={CHART_HEIGHT}>
        <BarChart
          data={data}
          margin={{ top: 8, right: 24, left: 0, bottom: 8 }}
          aria-label="Graphique d'adoption par profil utilisateur"
        >
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(0,0,0,0.06)" />
          <XAxis
            dataKey="profile"
            tick={{ fontSize: 13 }}
            tickLine={false}
            axisLine={{ stroke: 'rgba(0,0,0,0.06)' }}
          />
          <YAxis
            allowDecimals={false}
            tick={{ fontSize: 13 }}
            tickLine={false}
            axisLine={false}
          />
          <Tooltip content={<CustomTooltip />} />
          <Bar dataKey="count" name="Exécutions" fill="#3B82F6" radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </Card>
  );
}

export default AdoptionByProfileChart;

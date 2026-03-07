/**
 * CatalogueEvolutionChart - Line chart showing catalogue evolution over time.
 * Story 60.4, AC: 1, 2, 4, 5, 8.
 *
 * Uses recharts LineChart pattern from TrendLineChart.tsx.
 * X=week_start (formatted DD/MM), lines: created_count and published_count.
 */

import { Card, Empty, Skeleton } from 'antd';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';
import type { StatsCatalogueEvolutionPoint } from '../../../types/api';

export interface CatalogueEvolutionChartProps {
  data: StatsCatalogueEvolutionPoint[];
  loading?: boolean;
}

const CHART_HEIGHT = 280;

function formatAxisDate(dateStr: string): string {
  const d = new Date(dateStr + 'T00:00:00');
  return d.toLocaleDateString('fr-FR', { day: '2-digit', month: '2-digit' });
}

function CustomTooltip(props: { active?: boolean; payload?: Array<{ name: string; value: number; color: string }>; label?: string }) {
  const { active, payload, label } = props;
  if (!active || !payload?.length) return null;
  return (
    <div style={{ fontSize: 13 }}>
      <div style={{ fontWeight: 600, marginBottom: 4 }}>Semaine : {label}</div>
      {payload.map((entry, index) => (
        <div key={index} style={{ color: entry.color }}>
          {entry.name === 'created_count' ? 'Créées' : 'Publiées'} : {entry.value ?? 0}
        </div>
      ))}
    </div>
  );
}

export function CatalogueEvolutionChart({ data, loading = false }: CatalogueEvolutionChartProps) {
  if (loading) {
    return (
      <Card title={<span style={{ fontSize: 15, fontWeight: 600 }}>Évolution du catalogue</span>} size="small">
        <Skeleton active paragraph={{ rows: 5 }} />
      </Card>
    );
  }

  if (!data.length) {
    return (
      <Card title={<span style={{ fontSize: 15, fontWeight: 600 }}>Évolution du catalogue</span>} size="small">
        <Empty description="Aucune donnée d'évolution" image={Empty.PRESENTED_IMAGE_SIMPLE} />
      </Card>
    );
  }

  const chartData = data.map((p) => ({ ...p, dateLabel: formatAxisDate(p.week_start) }));

  return (
    <Card title={<span style={{ fontSize: 15, fontWeight: 600 }}>Évolution du catalogue</span>} size="small">
      <ResponsiveContainer width="100%" height={CHART_HEIGHT}>
        <LineChart
          data={chartData}
          margin={{ top: 8, right: 16, left: 0, bottom: 8 }}
          aria-label="Graphique d'évolution du catalogue par semaine"
        >
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(0,0,0,0.06)" />
          <XAxis
            dataKey="dateLabel"
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
          <Legend
            wrapperStyle={{ fontSize: 13 }}
            formatter={(value) => (value === 'created_count' ? 'Créées' : 'Publiées')}
          />
          <Line
            type="monotone"
            dataKey="created_count"
            name="created_count"
            stroke="#3B82F6"
            strokeWidth={2}
            dot={{ r: 3 }}
            activeDot={{ r: 5 }}
          />
          <Line
            type="monotone"
            dataKey="published_count"
            name="published_count"
            stroke="#10B981"
            strokeWidth={2}
            dot={{ r: 3 }}
            activeDot={{ r: 5 }}
          />
        </LineChart>
      </ResponsiveContainer>
    </Card>
  );
}

export default CatalogueEvolutionChart;

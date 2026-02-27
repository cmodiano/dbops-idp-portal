/**
 * ExecutionsChart - Line chart showing executions over time (success vs failure).
 *
 * Uses recharts: X = date, Y = count, two lines (Succès, Échec).
 */

import { Card, Skeleton } from 'antd';
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
import type { DashboardTimeSeriesPoint } from '../../types/api';

export interface ExecutionsChartProps {
  /** Time series data (date, success, failed per day). */
  data: DashboardTimeSeriesPoint[];
  /** Whether the chart is loading. */
  loading?: boolean;
}

/** Format date for X axis (e.g. "30/01"). */
function formatAxisDate(dateStr: string): string {
  const d = new Date(dateStr + 'T00:00:00');
  return d.toLocaleDateString('fr-FR', { day: '2-digit', month: '2-digit' });
}

export function ExecutionsChart({ data, loading = false }: ExecutionsChartProps) {
  if (loading) {
    return (
      <Card title={<span style={{ fontSize: 15, fontWeight: 600 }}>Exécutions dans le temps</span>} style={{ marginBottom: 24 }}>
        <Skeleton active paragraph={{ rows: 6 }} />
      </Card>
    );
  }

  const chartData = data.map((p) => ({
    ...p,
    dateLabel: formatAxisDate(p.date),
  }));

  return (
    <Card title={<span style={{ fontSize: 15, fontWeight: 600 }}>Exécutions dans le temps</span>} style={{ marginBottom: 24 }}>
      <ResponsiveContainer width="100%" height={280}>
        <LineChart
          data={chartData}
          margin={{ top: 8, right: 16, left: 0, bottom: 8 }}
          aria-label="Graphique des exécutions par jour : succès et échecs"
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
          <Tooltip
            labelFormatter={(label) => `Date: ${label}`}
            formatter={(value: number | undefined, name: string | undefined) => [
              value ?? 0,
              name === 'success' ? 'Succès' : 'Échecs',
            ]}
            contentStyle={{ fontSize: 13 }}
            labelStyle={{ fontWeight: 600 }}
          />
          <Legend
            wrapperStyle={{ fontSize: 13 }}
            formatter={(value) => (value === 'success' ? 'Succès' : 'Échecs')}
          />
          <Line
            type="monotone"
            dataKey="success"
            name="success"
            stroke="#10B981"
            strokeWidth={2}
            dot={{ r: 3 }}
            activeDot={{ r: 5 }}
          />
          <Line
            type="monotone"
            dataKey="failed"
            name="failed"
            stroke="#EF4444"
            strokeWidth={2}
            dot={{ r: 3 }}
            activeDot={{ r: 5 }}
          />
        </LineChart>
      </ResponsiveContainer>
    </Card>
  );
}

export default ExecutionsChart;

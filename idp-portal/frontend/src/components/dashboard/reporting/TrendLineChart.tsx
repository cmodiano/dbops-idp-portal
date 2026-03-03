/**
 * TrendLineChart - Line chart showing execution trends over time.
 * Story 8.3, AC5.
 *
 * Reuses ExecutionsChart pattern for success/failure lines.
 * Supports configurable period via days prop.
 *
 * TODO (AC5 optional): Add toggle to display trends by technology (one line per engine).
 * This would require a new API endpoint returning time series grouped by engine.
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
import type { DashboardTimeSeriesPoint } from '../../../types/api';

export interface TrendLineChartProps {
  /** Time series data (date, success, failed per day). */
  data: DashboardTimeSeriesPoint[];
  /** Whether the chart is loading. */
  loading?: boolean;
}

/** Chart height constant. */
const CHART_HEIGHT = 280;

/** Format date for X axis (e.g. "30/01"). */
function formatAxisDate(dateStr: string): string {
  const d = new Date(dateStr + 'T00:00:00');
  return d.toLocaleDateString('fr-FR', { day: '2-digit', month: '2-digit' });
}

/** Custom tooltip. */
function CustomTooltip(props: { active?: boolean; payload?: Array<{ name: string; value: number; color: string }>; label?: string }) {
  const { active, payload, label } = props;
  if (!active || !payload?.length) return null;
  return (
    <div style={{ fontSize: 13 }}>
      <div style={{ fontWeight: 600, marginBottom: 4 }}>Date: {label}</div>
      {payload.map((entry, index) => (
        <div key={index} style={{ color: entry.color }}>
          {entry.name === 'success' ? 'Succès' : 'Échecs'}: {entry.value ?? 0}
        </div>
      ))}
    </div>
  );
}

export function TrendLineChart({ data, loading = false }: TrendLineChartProps) {
  if (loading) {
    return (
      <Card title={<span style={{ fontSize: 15, fontWeight: 600 }}>Tendances temporelles</span>} size="small">
        <Skeleton active paragraph={{ rows: 6 }} />
      </Card>
    );
  }

  if (!data.length) {
    return (
      <Card title={<span style={{ fontSize: 15, fontWeight: 600 }}>Tendances temporelles</span>} size="small">
        <Empty description="Aucune donnée sur la période" image={Empty.PRESENTED_IMAGE_SIMPLE} />
      </Card>
    );
  }

  const chartData = data.map((p) => ({
    ...p,
    dateLabel: formatAxisDate(p.date),
  }));

  return (
    <Card title={<span style={{ fontSize: 15, fontWeight: 600 }}>Tendances temporelles</span>} size="small">
      <ResponsiveContainer width="100%" height={CHART_HEIGHT}>
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
          <Tooltip content={<CustomTooltip />} />
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

export default TrendLineChart;

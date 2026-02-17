/**
 * PeriodComparisonChart - Bar chart for comparing aggregated metrics between two periods.
 * Story 8.6, AC4, AC8.
 *
 * Uses recharts BarChart with grouped bars for period comparison.
 * Shows aggregated metrics (not daily trends) since we compare total stats per period.
 */

import { Card, Empty, Skeleton } from 'antd';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';
import type { ComparisonResult } from '../../../types/api';

export interface PeriodComparisonChartProps {
  /** Comparison result data. */
  data: ComparisonResult | null;
  /** Whether the chart is loading. */
  loading?: boolean;
  /** Label for period 1. */
  period1Label?: string;
  /** Label for period 2. */
  period2Label?: string;
}

/** Colors for the two periods. */
const PERIOD1_COLOR = '#4096ff'; // Ant Design primary blue
const PERIOD2_COLOR = '#52c41a'; // Ant Design success green

/** Tooltip payload entry type. */
interface TooltipPayloadEntry {
  name: string;
  value: number | null;
  color: string;
}

/** Custom tooltip props. */
interface CustomTooltipProps {
  active?: boolean;
  payload?: TooltipPayloadEntry[];
  label?: string;
}

/** Custom tooltip. */
function CustomTooltip({ active, payload, label }: CustomTooltipProps) {
  if (!active || !payload?.length) return null;
  return (
    <div style={{
      background: 'var(--color-bg-elevated, #fff)',
      padding: '8px 12px',
      border: '1px solid var(--color-border-secondary, #d9d9d9)',
      borderRadius: 4,
      fontSize: 12,
    }}>
      <div style={{ fontWeight: 600, marginBottom: 4 }}>{label}</div>
      {payload.map((entry, index) => (
        <div key={index} style={{ color: entry.color }}>
          {entry.name}: {entry.value !== null ? entry.value.toFixed(1) : 'N/A'}
        </div>
      ))}
    </div>
  );
}

export function PeriodComparisonChart({
  data,
  loading = false,
  period1Label = 'Période 1',
  period2Label = 'Période 2',
}: PeriodComparisonChartProps) {
  if (loading) {
    return (
      <Card title="Comparaison des tendances" size="small">
        <Skeleton active paragraph={{ rows: 6 }} />
      </Card>
    );
  }

  if (!data) {
    return (
      <Card title="Comparaison des tendances" size="small">
        <Empty description="Sélectionnez deux périodes à comparer" image={Empty.PRESENTED_IMAGE_SIMPLE} />
      </Card>
    );
  }

  // Period comparison displays aggregated metrics as grouped bars
  // Each metric is shown side-by-side for visual comparison
  const chartData = [
    { metric: 'Taux de succès (%)', period1: data.value1_stats.success_rate, period2: data.value2_stats.success_rate },
    { metric: 'Temps moyen (s)', period1: data.value1_stats.avg_time, period2: data.value2_stats.avg_time },
    { metric: 'Exécutions', period1: data.value1_stats.execution_count, period2: data.value2_stats.execution_count },
    { metric: 'Incidents', period1: data.value1_stats.incident_count, period2: data.value2_stats.incident_count },
  ];

  return (
    <Card title={`Comparaison: ${data.value1} vs ${data.value2}`} size="small">
      <ResponsiveContainer width="100%" height={300}>
        <BarChart
          data={chartData}
          margin={{ top: 8, right: 24, left: 24, bottom: 8 }}
          layout="horizontal"
          aria-label={`Comparaison entre ${period1Label} et ${period2Label}`}
        >
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(0,0,0,0.06)" />
          <XAxis
            dataKey="metric"
            tick={{ fontSize: 12 }}
            tickLine={false}
            axisLine={{ stroke: 'rgba(0,0,0,0.06)' }}
          />
          <YAxis
            tick={{ fontSize: 12 }}
            tickLine={false}
            axisLine={{ stroke: 'rgba(0,0,0,0.06)' }}
          />
          <Tooltip content={<CustomTooltip />} />
          <Legend />
          <Bar
            dataKey="period1"
            name={data.value1}
            fill={PERIOD1_COLOR}
            radius={[4, 4, 0, 0]}
          />
          <Bar
            dataKey="period2"
            name={data.value2}
            fill={PERIOD2_COLOR}
            radius={[4, 4, 0, 0]}
          />
        </BarChart>
      </ResponsiveContainer>
    </Card>
  );
}

export default PeriodComparisonChart;

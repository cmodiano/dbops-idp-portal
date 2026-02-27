/**
 * ComparisonChart - Grouped bar chart for comparing two values.
 * Story 8.6, AC2, AC3, AC8.
 *
 * Uses recharts BarChart with grouped bars (one bar per value).
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
import { STYLE_TOKENS } from '../../../theme/styleTokens';

export interface ComparisonChartProps {
  /** Comparison result data. */
  data: ComparisonResult | null;
  /** Whether the chart is loading. */
  loading?: boolean;
}

/** Colors for the two comparison values. */
const VALUE1_COLOR = '#4096ff'; // Ant Design primary blue
const VALUE2_COLOR = STYLE_TOKENS.iconSuccess; // #16a34a, ratio ~3.15:1 ✅ WCAG AA non-texte

/** Metric labels in French. */
const METRIC_LABELS: Record<string, string> = {
  success_rate: 'Taux de succès (%)',
  avg_time: 'Temps moyen (s)',
  execution_count: 'Exécutions',
  incident_count: 'Incidents',
};

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
      fontSize: 13,
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

export function ComparisonChart({ data, loading = false }: ComparisonChartProps) {
  if (loading) {
    return (
      <Card title={<span style={{ fontSize: 15, fontWeight: 600 }}>Comparaison</span>} size="small">
        <Skeleton active paragraph={{ rows: 6 }} />
      </Card>
    );
  }

  if (!data) {
    return (
      <Card title={<span style={{ fontSize: 15, fontWeight: 600 }}>Comparaison</span>} size="small">
        <Empty description="Sélectionnez deux valeurs à comparer" image={Empty.PRESENTED_IMAGE_SIMPLE} />
      </Card>
    );
  }

  // Transform data for grouped bar chart
  const chartData = [
    {
      name: METRIC_LABELS.success_rate,
      value1: data.value1_stats.success_rate,
      value2: data.value2_stats.success_rate,
    },
    {
      name: METRIC_LABELS.avg_time,
      value1: data.value1_stats.avg_time,
      value2: data.value2_stats.avg_time,
    },
    {
      name: METRIC_LABELS.execution_count,
      value1: data.value1_stats.execution_count,
      value2: data.value2_stats.execution_count,
    },
    {
      name: METRIC_LABELS.incident_count,
      value1: data.value1_stats.incident_count,
      value2: data.value2_stats.incident_count,
    },
  ];

  return (
    <Card title={<span style={{ fontSize: 15, fontWeight: 600 }}>Comparaison graphique</span>} size="small">
      <ResponsiveContainer width="100%" height={300}>
        <BarChart
          data={chartData}
          layout="vertical"
          margin={{ top: 8, right: 24, left: 120, bottom: 8 }}
          aria-label={`Comparaison entre ${data.value1} et ${data.value2}`}
        >
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(0,0,0,0.06)" horizontal={false} />
          <XAxis
            type="number"
            tick={{ fontSize: 13 }}
            tickLine={false}
            axisLine={{ stroke: 'rgba(0,0,0,0.06)' }}
          />
          <YAxis
            type="category"
            dataKey="name"
            tick={{ fontSize: 13 }}
            tickLine={false}
            axisLine={false}
            width={110}
          />
          <Tooltip content={<CustomTooltip />} />
          <Legend wrapperStyle={{ fontSize: 13 }} />
          <Bar
            dataKey="value1"
            name={data.value1}
            fill={VALUE1_COLOR}
            radius={[0, 4, 4, 0]}
          />
          <Bar
            dataKey="value2"
            name={data.value2}
            fill={VALUE2_COLOR}
            radius={[0, 4, 4, 0]}
          />
        </BarChart>
      </ResponsiveContainer>
    </Card>
  );
}

export default ComparisonChart;

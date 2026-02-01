/**
 * TechnologyBarChart - Horizontal bar chart showing executions by technology/engine.
 * Story 8.3, AC3.
 *
 * Uses recharts BarChart with horizontal layout (layout="vertical").
 * Reuses ENGINE_COLORS pattern from EngineBarChart (Story 8.2).
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
import type { TechnologyStats } from '../../../types/api';

export interface TechnologyBarChartProps {
  /** Technology stats data. */
  data: TechnologyStats[];
  /** Whether the chart is loading. */
  loading?: boolean;
}

/** Engine color palette (consistent with Story 8.2 design system). */
const ENGINE_COLORS: Record<string, string> = {
  Oracle: '#EF4444',      // rouge
  'SQL Server': '#0EA5E9', // bleu
  DB2: '#7C3AED',          // violet
  PostgreSQL: '#10B981',   // vert
  MySQL: '#F97316',        // orange
  'N/A': '#6B7280',        // gris
};

/** Get color for an engine (fallback to gray). */
function getEngineColor(engine: string): string {
  return ENGINE_COLORS[engine] ?? ENGINE_COLORS['N/A'];
}

/** Chart sizing constants. */
const MIN_CHART_HEIGHT = 200;
const BAR_HEIGHT_PER_ITEM = 50;

/** Custom tooltip content with count and success rate. */
function CustomTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  const data = payload[0]?.payload as TechnologyStats;
  return (
    <div style={{
      background: 'var(--color-bg-elevated, #fff)',
      padding: '8px 12px',
      border: '1px solid var(--color-border-secondary, #d9d9d9)',
      borderRadius: 4,
      fontSize: 12,
    }}>
      <div style={{ fontWeight: 600, marginBottom: 4 }}>{label}</div>
      <div>Executions: {data.count}</div>
      {data.success_rate !== null && (
        <div>Taux de succes: {data.success_rate.toFixed(1)}%</div>
      )}
    </div>
  );
}

export function TechnologyBarChart({ data, loading = false }: TechnologyBarChartProps) {
  if (loading) {
    return (
      <Card title="Repartition par technologie" size="small">
        <Skeleton active paragraph={{ rows: 4 }} />
      </Card>
    );
  }

  if (!data.length) {
    return (
      <Card title="Repartition par technologie" size="small">
        <Empty description="Aucune execution sur la periode" image={Empty.PRESENTED_IMAGE_SIMPLE} />
      </Card>
    );
  }

  return (
    <Card title="Repartition par technologie" size="small">
      <ResponsiveContainer width="100%" height={Math.max(MIN_CHART_HEIGHT, data.length * BAR_HEIGHT_PER_ITEM)}>
        <BarChart
          data={data}
          layout="vertical"
          margin={{ top: 8, right: 24, left: 0, bottom: 8 }}
          aria-label="Graphique des executions par technologie"
        >
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(0,0,0,0.06)" horizontal={false} />
          <XAxis
            type="number"
            tick={{ fontSize: 12 }}
            tickLine={false}
            axisLine={{ stroke: 'rgba(0,0,0,0.06)' }}
            allowDecimals={false}
          />
          <YAxis
            type="category"
            dataKey="engine"
            tick={{ fontSize: 12 }}
            tickLine={false}
            axisLine={false}
            width={100}
          />
          <Tooltip content={<CustomTooltip />} />
          <Bar dataKey="count" name="Executions" radius={[0, 4, 4, 0]}>
            {data.map((entry, index) => (
              <Cell key={`cell-${index}`} fill={getEngineColor(entry.engine)} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </Card>
  );
}

export default TechnologyBarChart;

/**
 * EngineBarChart - Horizontal bar chart showing executions by database engine.
 * Story 8.2, AC1, Task 7.
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
import type { EngineExecutions } from '../../../types/api';

export interface EngineBarChartProps {
  /** Executions data by engine. */
  data: EngineExecutions[];
  /** Whether the chart is loading. */
  loading?: boolean;
}

/** Engine color palette (consistent with design system). */
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

export function EngineBarChart({ data, loading = false }: EngineBarChartProps) {
  if (loading) {
    return (
      <Card title={<span style={{ fontSize: 15, fontWeight: 600 }}>Exécutions par moteur</span>} size="small">
        <Skeleton active paragraph={{ rows: 4 }} />
      </Card>
    );
  }

  if (!data.length) {
    return (
      <Card title={<span style={{ fontSize: 15, fontWeight: 600 }}>Exécutions par moteur</span>} size="small">
        <Empty description="Aucune exécution" image={Empty.PRESENTED_IMAGE_SIMPLE} />
      </Card>
    );
  }

  return (
    <Card title={<span style={{ fontSize: 15, fontWeight: 600 }}>Exécutions par moteur</span>} size="small">
      <ResponsiveContainer width="100%" height={Math.max(MIN_CHART_HEIGHT, data.length * BAR_HEIGHT_PER_ITEM)}>
        <BarChart
          data={data}
          layout="vertical"
          margin={{ top: 8, right: 24, left: 0, bottom: 8 }}
          aria-label="Graphique des exécutions par moteur de base de données"
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
            dataKey="engine"
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
            {data.map((entry, index) => (
              <Cell key={`cell-${index}`} fill={getEngineColor(entry.engine)} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </Card>
  );
}

export default EngineBarChart;

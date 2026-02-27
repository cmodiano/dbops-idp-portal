/**
 * AdoptionTrendChart - Line chart showing weekly adoption trend per engine.
 * Story 8.2, AC2, Task 9.
 *
 * Uses recharts LineChart with multiple series (one per engine).
 */

import { useMemo } from 'react';
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
import type { WeeklyTrendPoint } from '../../../types/api';

export interface AdoptionTrendChartProps {
  /** Weekly trend data (week_start, engine, count). */
  data: WeeklyTrendPoint[];
  /** Whether the chart is loading. */
  loading?: boolean;
}

/** Engine color palette (consistent with EngineBarChart). */
const ENGINE_COLORS: Record<string, string> = {
  Oracle: '#EF4444',
  'SQL Server': '#0EA5E9',
  DB2: '#7C3AED',
  PostgreSQL: '#10B981',
  MySQL: '#F97316',
  'N/A': '#6B7280',
};

/** Get color for an engine (fallback to gray). */
function getEngineColor(engine: string): string {
  return ENGINE_COLORS[engine] ?? '#6B7280';
}

/** Format week start date for display (e.g., "Sem. 01" or "01/01"). */
function formatWeekLabel(dateStr: string): string {
  const d = new Date(dateStr + 'T00:00:00');
  return `${d.toLocaleDateString('fr-FR', { day: '2-digit', month: '2-digit' })}`;
}

/**
 * Transform flat trend data into pivoted format for recharts.
 * Input: [{ week_start, engine, count }, ...]
 * Output: [{ week: "01/01", Oracle: 10, "SQL Server": 5 }, ...]
 */
function pivotTrendData(data: WeeklyTrendPoint[]): { chartData: Record<string, unknown>[]; engines: string[] } {
  const weekMap = new Map<string, Record<string, unknown>>();
  const engineSet = new Set<string>();

  for (const point of data) {
    engineSet.add(point.engine);
    const weekLabel = formatWeekLabel(point.week_start);
    const existing = weekMap.get(point.week_start) ?? { week: weekLabel, week_start: point.week_start };
    existing[point.engine] = point.count;
    weekMap.set(point.week_start, existing);
  }

  // Sort by week_start date
  const chartData = Array.from(weekMap.values()).sort((a, b) =>
    String(a.week_start).localeCompare(String(b.week_start))
  );

  return {
    chartData,
    engines: Array.from(engineSet).sort(),
  };
}

export function AdoptionTrendChart({ data, loading = false }: AdoptionTrendChartProps) {
  const { chartData, engines } = useMemo(() => pivotTrendData(data), [data]);

  if (loading) {
    return (
      <Card title={<span style={{ fontSize: 15, fontWeight: 600 }}>Tendance d'adoption (par semaine)</span>} size="small">
        <Skeleton active paragraph={{ rows: 6 }} />
      </Card>
    );
  }

  if (!data.length || !chartData.length) {
    return (
      <Card title={<span style={{ fontSize: 15, fontWeight: 600 }}>Tendance d'adoption (par semaine)</span>} size="small">
        <Empty description="Aucune donnée" image={Empty.PRESENTED_IMAGE_SIMPLE} />
      </Card>
    );
  }

  return (
    <Card title={<span style={{ fontSize: 15, fontWeight: 600 }}>Tendance d'adoption (par semaine)</span>} size="small">
      <ResponsiveContainer width="100%" height={300}>
        <LineChart
          data={chartData}
          margin={{ top: 8, right: 24, left: 0, bottom: 8 }}
          aria-label="Graphique de tendance d'adoption par semaine et par moteur"
        >
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(0,0,0,0.06)" />
          <XAxis
            dataKey="week"
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
            contentStyle={{ fontSize: 13 }}
            labelStyle={{ fontWeight: 600 }}
            formatter={(value: number | undefined, name: string | undefined) => [value ?? 0, name ?? '']}
          />
          <Legend wrapperStyle={{ fontSize: 13 }} />
          {engines.map((engine) => (
            <Line
              key={engine}
              type="monotone"
              dataKey={engine}
              name={engine}
              stroke={getEngineColor(engine)}
              strokeWidth={2}
              dot={{ r: 3 }}
              activeDot={{ r: 5 }}
              connectNulls
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </Card>
  );
}

export default AdoptionTrendChart;

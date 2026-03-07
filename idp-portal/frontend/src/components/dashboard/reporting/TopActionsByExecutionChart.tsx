/**
 * TopActionsByExecutionChart - Horizontal bar chart for top actions by execution count.
 * Story 60.10, AC: 2.
 * Pattern follows CatalogueItemTypeChart.tsx exactly.
 */
import { Card, Empty, Skeleton } from 'antd';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from 'recharts';
import type { StatsOperationsActionItem } from '../../../types/api';

export interface TopActionsByExecutionChartProps {
  data: StatsOperationsActionItem[];
  loading?: boolean;
}

const MIN_CHART_HEIGHT = 200;
const BAR_HEIGHT_PER_ITEM = 50;
const TITLE = 'Top actions — exécutions';
const FILL_COLOR = '#3B82F6';

export function TopActionsByExecutionChart({ data, loading = false }: TopActionsByExecutionChartProps) {
  if (loading) {
    return (
      <Card title={<span style={{ fontSize: 15, fontWeight: 600 }}>{TITLE}</span>} size="small">
        <Skeleton active paragraph={{ rows: 5 }} />
      </Card>
    );
  }

  if (!data.length) {
    return (
      <Card title={<span style={{ fontSize: 15, fontWeight: 600 }}>{TITLE}</span>} size="small">
        <Empty description="Aucune donnée" image={Empty.PRESENTED_IMAGE_SIMPLE} />
      </Card>
    );
  }

  return (
    <Card title={<span style={{ fontSize: 15, fontWeight: 600 }}>{TITLE}</span>} size="small">
      <div aria-label="Graphique des top actions par nombre d'exécutions">
        <ResponsiveContainer
          width="100%"
          height={Math.max(MIN_CHART_HEIGHT, data.length * BAR_HEIGHT_PER_ITEM)}
        >
          <BarChart
            data={data}
            layout="vertical"
            margin={{ top: 8, right: 24, left: 0, bottom: 8 }}
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
              dataKey="action_name"
              tick={{ fontSize: 13 }}
              tickLine={false}
              axisLine={false}
              width={160}
            />
            <Tooltip
              formatter={(value: number | undefined) => [value ?? 0, 'Exécutions']}
              contentStyle={{ fontSize: 13 }}
              labelStyle={{ fontWeight: 600 }}
            />
            <Bar dataKey="execution_count" name="Exécutions" fill={FILL_COLOR} radius={[0, 4, 4, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </Card>
  );
}

export default TopActionsByExecutionChart;

/**
 * CatalogueItemTypeChart - Horizontal bar chart showing catalogue items by type.
 * Story 60.4, AC: 1, 2, 4, 5, 8.
 *
 * Uses recharts BarChart with horizontal layout (layout="vertical").
 * Pattern follows TechnologyBarChart.tsx exactly.
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
import type { StatsCatalogueByItemType } from '../../../types/api';

export interface CatalogueItemTypeChartProps {
  data: StatsCatalogueByItemType[];
  loading?: boolean;
}

const ITEM_TYPE_COLORS: Record<string, string> = {
  action: '#3B82F6',
  workflow: '#8B5CF6',
};
const DEFAULT_COLOR = '#6B7280';

function getItemTypeColor(itemType: string): string {
  return ITEM_TYPE_COLORS[itemType] ?? DEFAULT_COLOR;
}

const MIN_CHART_HEIGHT = 200;
const BAR_HEIGHT_PER_ITEM = 50;

function CustomTooltip({ active, payload, label }: { active?: boolean; payload?: Array<{ payload: StatsCatalogueByItemType }>; label?: string }) {
  if (!active || !payload?.length) return null;
  const data = payload[0]?.payload as StatsCatalogueByItemType;
  return (
    <div style={{ fontSize: 13 }}>
      <div style={{ fontWeight: 600, marginBottom: 4 }}>{label}</div>
      <div>Nombre : {data.count}</div>
    </div>
  );
}

export function CatalogueItemTypeChart({ data, loading = false }: CatalogueItemTypeChartProps) {
  if (loading) {
    return (
      <Card title={<span style={{ fontSize: 15, fontWeight: 600 }}>Répartition actions / workflows</span>} size="small">
        <Skeleton active paragraph={{ rows: 3 }} />
      </Card>
    );
  }

  if (!data.length) {
    return (
      <Card title={<span style={{ fontSize: 15, fontWeight: 600 }}>Répartition actions / workflows</span>} size="small">
        <Empty description="Aucune donnée de catalogue" image={Empty.PRESENTED_IMAGE_SIMPLE} />
      </Card>
    );
  }

  return (
    <Card title={<span style={{ fontSize: 15, fontWeight: 600 }}>Répartition actions / workflows</span>} size="small">
      <ResponsiveContainer width="100%" height={Math.max(MIN_CHART_HEIGHT, data.length * BAR_HEIGHT_PER_ITEM)}>
        <BarChart
          data={data}
          layout="vertical"
          margin={{ top: 8, right: 24, left: 0, bottom: 8 }}
          aria-label="Graphique de répartition des actions et workflows"
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
            dataKey="item_type"
            tick={{ fontSize: 13 }}
            tickLine={false}
            axisLine={false}
            width={100}
          />
          <Tooltip content={<CustomTooltip />} />
          <Bar dataKey="count" name="Items" radius={[0, 4, 4, 0]}>
            {data.map((entry, index) => (
              <Cell key={`cell-${index}`} fill={getItemTypeColor(entry.item_type)} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </Card>
  );
}

export default CatalogueItemTypeChart;

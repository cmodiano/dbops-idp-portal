/**
 * ApprobationsRatioChart - Bar chart showing approved vs rejected executions.
 * Story 60.10, AC: 4.
 * Uses vertical bar chart (default recharts layout).
 */
import { Card, Empty, Skeleton } from 'antd';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell,
} from 'recharts';

export interface ApprobationsRatioChartProps {
  approved: number;
  rejected: number;
  approvalRate: number | null;
  loading?: boolean;
}

const TITLE = 'Répartition des approbations';
const COLORS = ['#10B981', '#EF4444']; // Approuvées, Rejetées

export function ApprobationsRatioChart({ approved, rejected, approvalRate, loading = false }: ApprobationsRatioChartProps) {
  if (loading) {
    return (
      <Card title={<span style={{ fontSize: 15, fontWeight: 600 }}>{TITLE}</span>} size="small">
        <Skeleton active paragraph={{ rows: 3 }} />
      </Card>
    );
  }

  if (approved === 0 && rejected === 0) {
    return (
      <Card title={<span style={{ fontSize: 15, fontWeight: 600 }}>{TITLE}</span>} size="small">
        <Empty description="Aucune approbation sur la période" image={Empty.PRESENTED_IMAGE_SIMPLE} />
      </Card>
    );
  }

  const chartData = [
    { label: 'Approuvées', count: approved },
    { label: 'Rejetées', count: rejected },
  ];

  return (
    <Card title={<span style={{ fontSize: 15, fontWeight: 600 }}>{TITLE}</span>} size="small">
      <div aria-label="Graphique de répartition des approbations">
        <ResponsiveContainer width="100%" height={220}>
          <BarChart
            data={chartData}
            margin={{ top: 8, right: 24, left: 0, bottom: 8 }}
          >
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(0,0,0,0.06)" vertical={false} />
            <XAxis
              dataKey="label"
              tick={{ fontSize: 13 }}
              tickLine={false}
              axisLine={{ stroke: 'rgba(0,0,0,0.06)' }}
            />
            <YAxis
              tick={{ fontSize: 13 }}
              tickLine={false}
              axisLine={false}
              allowDecimals={false}
            />
            <Tooltip
              formatter={(value: number | undefined, name: string | undefined) => {
                const v = value ?? 0;
                const total = approved + rejected;
                const pct = total > 0 ? ((v / total) * 100).toFixed(1) : '0.0';
                return [`${v} (${pct} %)`, name ?? ''];
              }}
              contentStyle={{ fontSize: 13 }}
              labelStyle={{ fontWeight: 600 }}
            />
            <Bar dataKey="count" name="Approbations" radius={[4, 4, 0, 0]}>
              {chartData.map((_, index) => (
                <Cell key={`cell-${index}`} fill={COLORS[index]} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
      {approvalRate !== null && (
        <div style={{ textAlign: 'center', fontSize: 12, color: '#6B7280', marginTop: 4 }}>
          Taux d&apos;approbation : {approvalRate.toFixed(1)} %
        </div>
      )}
    </Card>
  );
}

export default ApprobationsRatioChart;

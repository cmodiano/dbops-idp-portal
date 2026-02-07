/**
 * ComparisonExecutionsDrawer - Drawer showing filtered executions for drill-down.
 * Story 8.6, AC6.
 *
 * Opens when clicking on a comparison metric to show related executions.
 */

import { Drawer, Table, Tag, Empty, Button } from 'antd';
import type { TableProps } from 'antd';
import { Link } from 'react-router';

import type { ComparisonDimension, ComparisonMetric, DashboardRecentExecution } from '../../../types/api';

export interface ComparisonExecutionsDrawerProps {
  /** Whether the drawer is open. */
  open: boolean;
  /** Callback to close the drawer. */
  onClose: () => void;
  /** Comparison dimension. */
  dimension?: ComparisonDimension;
  /** First value being compared. */
  value1?: string;
  /** Second value being compared. */
  value2?: string;
  /** Metric being drilled down. */
  metric?: ComparisonMetric;
  /** Executions data (filtered). */
  executions?: DashboardRecentExecution[];
  /** Whether data is loading. */
  loading?: boolean;
}

/** Status tag colors. */
const STATUS_COLORS: Record<string, string> = {
  COMPLETED: 'green',
  FAILED: 'red',
  RUNNING: 'blue',
  PENDING: 'default',
  SUBMITTED: 'processing',
  CANCELLED: 'default',
  PENDING_APPROVAL: 'orange',
  REJECTED: 'red',
};

/** Metric labels. */
const METRIC_LABELS: Record<ComparisonMetric, string> = {
  success_rate: 'Taux de succès',
  avg_time: 'Temps moyen',
  execution_count: 'Nombre d\'exécutions',
  incident_count: 'Incidents',
};

const columns: TableProps<DashboardRecentExecution>['columns'] = [
  {
    title: 'Action',
    dataIndex: 'action_name',
    key: 'action_name',
    ellipsis: true,
    render: (text) => text || 'N/A',
  },
  {
    title: 'Environnement',
    dataIndex: 'environment',
    key: 'environment',
    width: 100,
    render: (env) => <Tag>{env}</Tag>,
  },
  {
    title: 'Statut',
    dataIndex: 'status',
    key: 'status',
    width: 120,
    render: (status) => <Tag color={STATUS_COLORS[status] || 'default'}>{status}</Tag>,
  },
  {
    title: 'Durée',
    key: 'duration',
    width: 80,
    render: () => '-', // Would need started_at/completed_at to calculate
  },
  {
    title: 'Date',
    dataIndex: 'created_at',
    key: 'created_at',
    width: 150,
    render: (date) => date ? new Date(date).toLocaleString('fr-FR') : '-',
  },
  {
    title: '',
    key: 'action',
    width: 80,
    render: (_, record) => (
      <Link to={`/executions/${record.id}`}>
        <Button type="link" size="small">Détail</Button>
      </Link>
    ),
  },
];

export function ComparisonExecutionsDrawer({
  open,
  onClose,
  value1,
  value2,
  metric,
  executions = [],
  loading = false,
}: ComparisonExecutionsDrawerProps) {
  const title = metric
    ? `Exécutions - ${METRIC_LABELS[metric]}`
    : 'Exécutions';

  const subtitle = value1 && value2
    ? `${value1} vs ${value2}`
    : '';

  return (
    <Drawer
      title={
        <div>
          <div>{title}</div>
          {subtitle && <div style={{ fontSize: 12, fontWeight: 'normal', color: '#8c8c8c' }}>{subtitle}</div>}
        </div>
      }
      placement="right"
      width={640}
      open={open}
      onClose={onClose}
      styles={{ body: { padding: 16 } }}
    >
      {executions.length === 0 && !loading ? (
        <Empty description="Aucune exécution trouvée pour ces critères" />
      ) : (
        <Table
          columns={columns}
          dataSource={executions}
          rowKey="id"
          loading={loading}
          size="small"
          pagination={{ pageSize: 10 }}
          scroll={{ x: 'max-content' }}
        />
      )}
    </Drawer>
  );
}

export default ComparisonExecutionsDrawer;

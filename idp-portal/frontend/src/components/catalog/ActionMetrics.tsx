/**
 * ActionMetrics - Scorecard component for action performance metrics (Story 8.1, AC1, AC2, AC3).
 *
 * Displays 4 statistics in a grid layout:
 * - Success rate (%) with color coding: green (>95%), orange (80-95%), red (<80%)
 * - Average execution time (formatted as seconds/minutes)
 * - Total executions count
 * - Incidents count (failed executions)
 *
 * When stats is null or total_executions is 0, displays "Pas encore de donnees" message.
 */

import { Row, Col, Statistic, Empty, theme } from 'antd';
import type { GlobalToken } from 'antd';
import {
  CheckCircleOutlined,
  ClockCircleOutlined,
  PlayCircleOutlined,
  WarningOutlined,
} from '@ant-design/icons';
import type { ActionStats } from '../../types/api';

export interface ActionMetricsProps {
  /** Action stats from API (null if no data). */
  stats: ActionStats | null | undefined;
  /** Loading state for skeleton display. */
  loading?: boolean;
}

/**
 * Get color for success rate based on threshold (AC2).
 * - Green: > 95%
 * - Orange: 80-95%
 * - Red: < 80%
 */
function getSuccessRateColor(rate: number | null, token: GlobalToken): string {
  if (rate === null) return token.colorTextSecondary;
  if (rate >= 95) return token.colorSuccess;
  if (rate >= 80) return token.colorWarning;
  return token.colorError;
}

/**
 * Format execution time from milliseconds to human-readable format.
 * - < 1000ms: "XXX ms"
 * - < 59.95s: "X.X s" (to avoid displaying "60.0 s" due to rounding)
 * - >= 59.95s: "X min Y s"
 */
function formatExecutionTime(ms: number | null): string {
  if (ms === null) return '-';
  if (ms < 1000) return `${ms} ms`;
  const seconds = ms / 1000;
  // Use 59.95 threshold to avoid "60.0 s" edge case after rounding
  if (seconds < 59.95) return `${seconds.toFixed(1)} s`;
  const minutes = Math.floor(seconds / 60);
  const remainingSeconds = Math.round(seconds % 60);
  return `${minutes} min ${remainingSeconds} s`;
}

export function ActionMetrics({ stats, loading }: ActionMetricsProps) {
  const { token } = theme.useToken();

  // AC3: Handle no data case
  if (!loading && (!stats || stats.total_executions === 0)) {
    return (
      <Empty
        description="Pas encore de donnees"
        image={Empty.PRESENTED_IMAGE_SIMPLE}
        style={{ margin: '16px 0' }}
        data-testid="action-metrics-empty"
      />
    );
  }

  const successRateColor = stats ? getSuccessRateColor(stats.success_rate, token) : token.colorTextSecondary;

  return (
    <Row gutter={[16, 16]} data-testid="action-metrics">
      <Col xs={12} sm={12} md={6}>
        <Statistic
          title="Taux de succes"
          value={stats?.success_rate ?? '-'}
          suffix={stats?.success_rate !== null ? '%' : ''}
          prefix={<CheckCircleOutlined />}
          styles={{ content: { color: successRateColor, fontSize: 20 } }}
          loading={loading}
        />
      </Col>
      <Col xs={12} sm={12} md={6}>
        <Statistic
          title="Temps moyen"
          value={formatExecutionTime(stats?.avg_execution_time_ms ?? null)}
          prefix={<ClockCircleOutlined />}
          styles={{ content: { fontSize: 20 } }}
          loading={loading}
        />
      </Col>
      <Col xs={12} sm={12} md={6}>
        <Statistic
          title="Executions"
          value={stats?.total_executions ?? 0}
          prefix={<PlayCircleOutlined />}
          styles={{ content: { fontSize: 20 } }}
          loading={loading}
        />
      </Col>
      <Col xs={12} sm={12} md={6}>
        <Statistic
          title="Incidents"
          value={stats?.incidents_count ?? 0}
          prefix={<WarningOutlined />}
          styles={{ content: { color: (stats?.incidents_count ?? 0) > 0 ? token.colorError : token.colorTextSecondary, fontSize: 20 } }}
          loading={loading}
        />
      </Col>
    </Row>
  );
}

export default ActionMetrics;

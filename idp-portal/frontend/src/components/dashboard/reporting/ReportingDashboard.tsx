/**
 * ReportingDashboard - Dashboard with statistics by technology and environment.
 * Story 8.3, AC1, AC2, AC6, AC8.
 *
 * Displays:
 * - Period selector (7, 14, 30, 90 days)
 * - StatCards row (executions today, success rate, in progress, errors)
 * - TechnologyBarChart and EnvironmentBarChart side by side
 * - TrendLineChart full width
 * - Link to Executions page (replaces removed Recent Executions table)
 */

import { useState, useEffect } from 'react';
import { Row, Col, Segmented, Alert, Space, Typography } from 'antd';
import { Link } from 'react-router';
import {
  RocketOutlined,
  CheckCircleOutlined,
  SyncOutlined,
  ExclamationCircleOutlined,
  ArrowRightOutlined,
} from '@ant-design/icons';
import { StatCard } from '../StatCard';
import { TechnologyBarChart } from './TechnologyBarChart';
import { EnvironmentBarChart } from './EnvironmentBarChart';
import { TrendLineChart } from './TrendLineChart';
import {
  fetchStats,
  fetchStatsByTechnology,
  fetchStatsByEnvironment,
  fetchTimeSeries,
} from '../../../services/dashboard_service';
import type {
  DashboardStats,
  TechnologyStats,
  EnvironmentStats,
  DashboardTimeSeriesPoint,
} from '../../../types/api';

const { Text } = Typography;

/** Period options for Segmented selector. */
const PERIOD_OPTIONS = [
  { label: '7 jours', value: 7 },
  { label: '14 jours', value: 14 },
  { label: '30 jours', value: 30 },
  { label: '90 jours', value: 90 },
];

export function ReportingDashboard() {
  const [period, setPeriod] = useState<number>(14);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Data states
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [techStats, setTechStats] = useState<TechnologyStats[]>([]);
  const [envStats, setEnvStats] = useState<EnvironmentStats[]>([]);
  const [timeSeries, setTimeSeries] = useState<DashboardTimeSeriesPoint[]>([]);

  useEffect(() => {
    let cancelled = false;

    async function loadData() {
      setLoading(true);
      setError(null);

      try {
        const [statsData, techData, envData, timeData] = await Promise.all([
          fetchStats(period),
          fetchStatsByTechnology(period),
          fetchStatsByEnvironment(period),
          fetchTimeSeries(period),
        ]);

        if (cancelled) return;

        setStats(statsData);
        setTechStats(techData);
        setEnvStats(envData);
        setTimeSeries(timeData);
      } catch (err) {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : 'Erreur lors du chargement');
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    loadData();

    return () => {
      cancelled = true;
    };
  }, [period]);

  return (
    <Space direction="vertical" size="middle" style={{ width: '100%' }}>
      {/* Period selector */}
      <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
        <Segmented
          options={PERIOD_OPTIONS}
          value={period}
          onChange={(val) => setPeriod(val as number)}
        />
      </div>

      {/* Error alert */}
      {error && (
        <Alert
          type="error"
          message="Erreur de chargement"
          description={error}
          showIcon
          closable
          onClose={() => setError(null)}
        />
      )}

      {/* StatCards row */}
      <Row gutter={[16, 16]}>
        <Col xs={24} sm={12} md={6}>
          <StatCard
            label="Executions du jour"
            value={stats?.executions_jour ?? 0}
            icon={<RocketOutlined />}
            loading={loading}
          />
        </Col>
        <Col xs={24} sm={12} md={6}>
          <StatCard
            label="Taux de succes"
            value={stats?.taux_succes_pct ?? 0}
            suffix="%"
            icon={<CheckCircleOutlined />}
            variant="success"
            loading={loading}
          />
        </Col>
        <Col xs={24} sm={12} md={6}>
          <StatCard
            label="En cours"
            value={stats?.executions_en_cours ?? 0}
            icon={<SyncOutlined spin={!loading && (stats?.executions_en_cours ?? 0) > 0} />}
            variant="inProgress"
            loading={loading}
          />
        </Col>
        <Col xs={24} sm={12} md={6}>
          <StatCard
            label="En erreur"
            value={stats?.executions_en_erreur ?? 0}
            icon={<ExclamationCircleOutlined />}
            variant="error"
            loading={loading}
          />
        </Col>
      </Row>

      {/* Bar charts row */}
      <Row gutter={[16, 16]}>
        <Col xs={24} md={12}>
          <TechnologyBarChart data={techStats} loading={loading} />
        </Col>
        <Col xs={24} md={12}>
          <EnvironmentBarChart data={envStats} loading={loading} />
        </Col>
      </Row>

      {/* Trend line chart */}
      <TrendLineChart data={timeSeries} loading={loading} />

      {/* Link to executions page (AC8) */}
      <div style={{ textAlign: 'center', marginTop: 8 }}>
        <Link to="/executions">
          <Text type="secondary">
            Voir toutes les executions <ArrowRightOutlined />
          </Text>
        </Link>
      </div>
    </Space>
  );
}

export default ReportingDashboard;

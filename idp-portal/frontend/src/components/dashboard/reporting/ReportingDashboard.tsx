/**
 * ReportingDashboard - Dashboard with statistics by technology and environment.
 * Story 8.3, AC1, AC2, AC6, AC8; Story 8.4 (advanced filters); Story 8.5 (export).
 *
 * Displays:
 * - Advanced filters panel (engine, environment, tags, status, date range)
 * - Period selector (7, 14, 30, 90 days) - disabled when custom date range is set
 * - Export button (CSV/PDF) - Story 8.5, AC1
 * - StatCards row (executions today, success rate, in progress, errors)
 * - TechnologyBarChart and EnvironmentBarChart side by side
 * - TrendLineChart full width
 * - Link to Executions page (replaces removed Recent Executions table)
 */

import { useState, useEffect, useCallback } from 'react';
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
import { AdvancedFiltersPanel } from './AdvancedFiltersPanel';
import { ExportButton } from './ExportButton';
import {
  fetchStats,
  fetchStatsByTechnology,
  fetchStatsByEnvironment,
  fetchTimeSeries,
  fetchFilterOptions,
} from '../../../services/dashboard_service';
import { useUrlFilters } from '../../../hooks/useUrlFilters';
import type {
  DashboardStats,
  TechnologyStats,
  EnvironmentStats,
  DashboardTimeSeriesPoint,
  DashboardFilters,
  FilterOptions,
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
  // URL-synced filters (Story 8.4, AC6, AC8)
  const [filters, setFilters] = useUrlFilters();

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filter options from API (Story 8.4, Task 14)
  const [filterOptions, setFilterOptions] = useState<FilterOptions | null>(null);

  // Data states
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [techStats, setTechStats] = useState<TechnologyStats[]>([]);
  const [envStats, setEnvStats] = useState<EnvironmentStats[]>([]);
  const [timeSeries, setTimeSeries] = useState<DashboardTimeSeriesPoint[]>([]);

  // Determine if custom date range is set (disables Segmented)
  const hasCustomDateRange = !!(filters.fromDate && filters.toDate);

  // Current period from filters or default
  const period = filters.days || 14;

  // Handle period change via Segmented
  const handlePeriodChange = useCallback(
    (value: number) => {
      setFilters({
        ...filters,
        days: value,
        // Clear custom date range when selecting preset period
        fromDate: undefined,
        toDate: undefined,
      });
    },
    [filters, setFilters],
  );

  // Handle filter changes from AdvancedFiltersPanel
  const handleFiltersChange = useCallback(
    (newFilters: DashboardFilters) => {
      setFilters(newFilters);
    },
    [setFilters],
  );

  // Load filter options on mount (Story 8.4, Task 14)
  useEffect(() => {
    fetchFilterOptions()
      .then(setFilterOptions)
      .catch(() => {
        // Silently fail - panel will use fallback options
      });
  }, []);

  // Load dashboard data when filters change
  useEffect(() => {
    let cancelled = false;

    async function loadData() {
      setLoading(true);
      setError(null);

      // Build API filters object
      const apiFilters: DashboardFilters = {
        ...filters,
        days: hasCustomDateRange ? undefined : period,
      };

      try {
        const [statsData, techData, envData, timeData] = await Promise.all([
          fetchStats(apiFilters),
          fetchStatsByTechnology(apiFilters),
          fetchStatsByEnvironment(apiFilters),
          fetchTimeSeries(apiFilters),
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
  }, [filters, hasCustomDateRange, period]);

  return (
    <Space direction="vertical" size="middle" style={{ width: '100%' }}>
      {/* Advanced filters panel (Story 8.4, AC1) */}
      <AdvancedFiltersPanel
        filters={filters}
        onFiltersChange={handleFiltersChange}
        loading={loading}
        filterOptions={filterOptions}
      />

      {/* Period selector and Export button - period disabled when custom date range is set */}
      <div style={{ display: 'flex', justifyContent: 'flex-end', alignItems: 'center', gap: 16 }}>
        {hasCustomDateRange && (
          <Text type="secondary" style={{ fontSize: 12 }}>
            Période personnalisée active
          </Text>
        )}
        <Segmented
          options={PERIOD_OPTIONS}
          value={period}
          onChange={(val) => handlePeriodChange(val as number)}
          disabled={hasCustomDateRange}
        />
        <ExportButton
          filters={filters}
          loading={loading}
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
            label="Exécutions du jour"
            value={stats?.executions_jour ?? 0}
            icon={<RocketOutlined />}
            loading={loading}
          />
        </Col>
        <Col xs={24} sm={12} md={6}>
          <StatCard
            label="Taux de succès"
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

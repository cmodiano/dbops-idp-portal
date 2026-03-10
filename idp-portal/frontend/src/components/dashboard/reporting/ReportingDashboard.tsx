/**
 * ReportingDashboard - Dashboard with advanced analytics and comparisons.
 * Story 8.3, AC1, AC2, AC6, AC8; Story 8.4 (advanced filters); Story 8.5 (export); Story 8.6 (comparison).
 * Story 9.4: StatCards moved to ExecutionsPage.
 * Story 71.1, AC6: Migration DIP — utilise useDashboardReportingStats au lieu d'importer directement dashboard_service.
 *
 * Displays:
 * - Mode selector: Stats vs Comparison (Story 8.6, AC1)
 * - Stats mode: Advanced filters, period selector, export, charts (StatCards moved to ExecutionsPage)
 * - Comparison mode: Panel to select dimension/values, comparison charts, delta badges
 * - Link to Executions page
 */

import { useState, useCallback } from 'react';
import { Row, Col, Segmented, Alert, Space, Typography } from 'antd';
import { Link, useNavigate } from 'react-router';
import { ArrowRightOutlined } from '@ant-design/icons';
import { TechnologyBarChart } from './TechnologyBarChart';
import { EnvironmentBarChart } from './EnvironmentBarChart';
import { TrendLineChart } from './TrendLineChart';
import { AdvancedFiltersPanel } from './AdvancedFiltersPanel';
import { ExportButton } from './ExportButton';
import { ComparisonModeSelector } from './ComparisonModeSelector';
import { ComparisonPanel } from './ComparisonPanel';
import { ComparisonChart } from './ComparisonChart';
import { PeriodComparisonChart } from './PeriodComparisonChart';
import { ComparisonSummaryCards } from './ComparisonSummaryCards';
import { ComparisonExecutionsDrawer } from './ComparisonExecutionsDrawer';
import { AdminPlatformSection } from './AdminPlatformSection';
import { OperationsActivitySection } from './OperationsActivitySection';
import { RecentExecutions } from '../RecentExecutions';
import { useDashboardReportingStats } from '../../../hooks/useDashboardStats';
import { useUrlFilters } from '../../../hooks/useUrlFilters';
import type {
  DashboardFilters,
  ComparisonDimension,
  ComparisonResult,
  ComparisonMetric,
  DashboardRecentExecution,
} from '../../../types/api';
import type { DashboardMode } from './ComparisonModeSelector';

const { Text } = Typography;

/** Period options for Segmented selector. */
const PERIOD_OPTIONS = [
  { label: '7 jours', value: 7 },
  { label: '14 jours', value: 14 },
  { label: '30 jours', value: 30 },
  { label: '90 jours', value: 90 },
];

export interface ReportingDashboardProps {
  /** Recent executions from WebSocket (Story 5.1, useDashboardWebSocket). */
  recentExecutions?: DashboardRecentExecution[];
}

export function ReportingDashboard({ recentExecutions = [] }: ReportingDashboardProps) {
  const navigate = useNavigate();

  // URL-synced filters (Story 8.4, AC6, AC8)
  const [filters, setFilters] = useUrlFilters();

  // Determine if custom date range is set (disables Segmented)
  const hasCustomDateRange = !!(filters.fromDate && filters.toDate);

  // Current period from filters or default
  const period = filters.days || 14;

  // Build API filters object (used by both data loading and child components)
  const apiFilters: DashboardFilters = {
    ...filters,
    days: hasCustomDateRange ? undefined : period,
  };

  // Story 71.1, AC6: All dashboard data fetching via hook
  const {
    techStats,
    envStats,
    timeSeries,
    filterOptions,
    loading,
    error,
    setError,
    compare,
  } = useDashboardReportingStats(apiFilters);

  // Comparison mode states (Story 8.6, AC1)
  const [mode, setMode] = useState<DashboardMode>('stats');
  const [comparisonResult, setComparisonResult] = useState<ComparisonResult | null>(null);
  const [comparisonLoading, setComparisonLoading] = useState(false);
  const [comparisonError, setComparisonError] = useState<string | null>(null);

  // Store last comparison parameters for drawer (Story 8.6, AC6)
  const [lastComparisonDimension, setLastComparisonDimension] = useState<ComparisonDimension>('technology');
  const [lastComparisonValue1, setLastComparisonValue1] = useState<string>('');
  const [lastComparisonValue2, setLastComparisonValue2] = useState<string>('');

  // Drill-down drawer state (Story 8.6, AC6)
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [drawerMetric, setDrawerMetric] = useState<ComparisonMetric | undefined>();

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

  // Handle comparison request (Story 8.6, AC2, AC3, AC4)
  const handleCompare = useCallback(async (
    dimension: ComparisonDimension,
    value1: string,
    value2: string,
    period1Start?: string,
    period1End?: string,
    period2Start?: string,
    period2End?: string,
  ) => {
    setComparisonLoading(true);
    setComparisonError(null);

    // Store for drawer drill-down
    setLastComparisonDimension(dimension);
    setLastComparisonValue1(value1);
    setLastComparisonValue2(value2);

    try {
      const result = await compare({
        dimension,
        value1,
        value2,
        days: dimension !== 'period' ? 14 : undefined,
        period1Start,
        period1End,
        period2Start,
        period2End,
      });
      setComparisonResult(result);
    } catch (err) {
      setComparisonError(err instanceof Error ? err.message : 'Erreur lors de la comparaison');
    } finally {
      setComparisonLoading(false);
    }
  }, [compare]);

  // Handle drill-down to executions (Story 8.6, AC6)
  const handleMetricClick = useCallback((metric: ComparisonMetric) => {
    setDrawerMetric(metric);
    setDrawerOpen(true);
  }, []);

  return (
    <Space orientation="vertical" size="middle" style={{ width: '100%' }}>
      {/* Mode selector: Stats vs Comparison (Story 8.6, AC1) */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <ComparisonModeSelector mode={mode} onModeChange={setMode} />
        {mode === 'stats' && (
          <ExportButton filters={filters} loading={loading} />
        )}
      </div>

      {mode === 'stats' ? (
        <>
          {/* Advanced filters panel (Story 8.4, AC1) */}
          <AdvancedFiltersPanel
            filters={filters}
            onFiltersChange={handleFiltersChange}
            loading={loading}
            filterOptions={filterOptions}
          />

          {/* Period selector - disabled when custom date range is set */}
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
          </div>

          {/* Error alert */}
          {error && (
            <Alert
              type="error"
              title="Erreur de chargement"
              description={error}
              showIcon
              closable
              onClose={() => setError(null)}
            />
          )}

          {/* Story 9.4: StatCards moved to ExecutionsPage */}

          {/* Exécutions récentes (WebSocket live updates) */}
          <RecentExecutions
            executions={recentExecutions}
            onRowClick={(exec) => navigate(`/executions/${exec.id}`)}
          />

          {/* Section admin — Utilisation de la plateforme (Story 60.3) */}
          <AdminPlatformSection filters={apiFilters} />

          {/* Section opérations — Activité opérationnelle (Story 60.9) */}
          <OperationsActivitySection filters={apiFilters} />

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
        </>
      ) : (
        <>
          {/* Comparison mode (Story 8.6) */}
          <ComparisonPanel
            filterOptions={filterOptions}
            loading={comparisonLoading}
            onCompare={handleCompare}
          />

          {/* Comparison error alert */}
          {comparisonError && (
            <Alert
              type="error"
              title="Erreur de comparaison"
              description={comparisonError}
              showIcon
              closable
              onClose={() => setComparisonError(null)}
            />
          )}

          {/* Comparison results (Story 8.6, AC5, AC8) */}
          {comparisonResult && (
            <>
              <ComparisonSummaryCards
                data={comparisonResult}
                loading={comparisonLoading}
                onMetricClick={handleMetricClick}
              />

              {lastComparisonDimension === 'period' ? (
                <PeriodComparisonChart
                  data={comparisonResult}
                  loading={comparisonLoading}
                />
              ) : (
                <ComparisonChart
                  data={comparisonResult}
                  loading={comparisonLoading}
                />
              )}
            </>
          )}
        </>
      )}

      {/* Drill-down drawer (Story 8.6, AC6) */}
      <ComparisonExecutionsDrawer
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        dimension={lastComparisonDimension}
        value1={lastComparisonValue1}
        value2={lastComparisonValue2}
        metric={drawerMetric}
        loading={comparisonLoading}
      />
    </Space>
  );
}

export default ReportingDashboard;

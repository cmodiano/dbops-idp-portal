/**
 * AdvancedFiltersPanel - Advanced filter controls for dashboard.
 * Story 8.4, AC1.
 *
 * Displays filter controls aligned with CalendarFiltersPanel / ExecutionsFiltersPanel:
 * - Engine (single-select)
 * - Environment (single-select)
 * - Tags (multi-select)
 * - Status (single-select)
 * - Date range picker (from_date / to_date)
 * - Reset button with active filter count badge
 */

import { Card, Form, Row, Col, Select, DatePicker, Button, Badge, Space, theme } from 'antd';
import { FilterOutlined, ClearOutlined } from '@ant-design/icons';
import type { Dayjs } from 'dayjs';
import dayjs from 'dayjs';
import type { DashboardFilters, DashboardFilterStatus, FilterOptions } from '../../../types/api';
import { getEnvironmentLabel, sortEnvironments } from '../../../utils/environmentHelpers';
import { EXECUTION_STATUS_FILTER_OPTIONS } from '../../../utils/execution-status';

const { RangePicker } = DatePicker;

/** Default engine options (fallback if API fails). */
const DEFAULT_ENGINE_OPTIONS = [
  { label: 'AAP', value: 'aap' },
  { label: 'Terraform', value: 'terraform' },
  { label: 'GitHub Actions', value: 'github_actions' },
  { label: 'Azure DevOps', value: 'azuredevops' },
];

// Story 13.7: DEFAULT_ENVIRONMENT_OPTIONS removed - use filterOptions from API or useEnvironments hook
// Fallback kept for backward compatibility but should use useEnvironments hook
const DEFAULT_ENVIRONMENT_OPTIONS = [
  { label: 'Développement', value: 'dev' },
  { label: 'Staging', value: 'staging' },
  { label: 'Production', value: 'prod' },
];

/** Dashboard status filter options: execution statuses + PENDING (DashboardFilterStatus includes PENDING). */
const DASHBOARD_STATUS_FILTER_OPTIONS: { label: string; value: DashboardFilterStatus }[] = [
  { label: 'En attente', value: 'PENDING' },
  ...EXECUTION_STATUS_FILTER_OPTIONS,
];

export interface AdvancedFiltersPanelProps {
  /** Current filter values. */
  filters: DashboardFilters;
  /** Callback when filters change. */
  onFiltersChange: (filters: DashboardFilters) => void;
  /** Loading state (disables inputs). */
  loading?: boolean;
  /** Dynamic filter options from API. */
  filterOptions?: FilterOptions | null;
}

/**
 * Count active filters (non-null/non-empty values).
 */
function countActiveFilters(filters: DashboardFilters): number {
  return [
    filters.engine,
    filters.environment,
    filters.tags && filters.tags.length > 0,
    filters.status,
    filters.fromDate || filters.toDate,
  ].filter(Boolean).length;
}

export function AdvancedFiltersPanel({
  filters,
  onFiltersChange,
  loading = false,
  filterOptions,
}: AdvancedFiltersPanelProps) {
  const { token } = theme.useToken();
  const activeFiltersCount = countActiveFilters(filters);

  // Build options from API or fallback
  const engineOptions = filterOptions?.engines?.length
    ? filterOptions.engines.map((e) => ({ label: e, value: e }))
    : DEFAULT_ENGINE_OPTIONS;

  const environmentOptions = filterOptions?.environments?.length
    ? (() => {
        const unique = [
          ...new Set(
            filterOptions.environments
              .map((e) => (e || '').toLowerCase().trim())
              .filter(Boolean),
          ),
        ];
        return sortEnvironments(unique).map((e) => ({
          label: getEnvironmentLabel(e),
          value: e,
        }));
      })()
    : DEFAULT_ENVIRONMENT_OPTIONS;

  const tagOptions = filterOptions?.tags?.length
    ? filterOptions.tags.map((t) => ({ label: t, value: t }))
    : [];

  const handleReset = () => {
    onFiltersChange({});
  };

  const handleEngineChange = (value: string | undefined) => {
    onFiltersChange({ ...filters, engine: value || undefined });
  };

  const handleEnvironmentChange = (value: string | undefined) => {
    onFiltersChange({ ...filters, environment: value || undefined });
  };

  const handleTagsChange = (values: string[]) => {
    onFiltersChange({ ...filters, tags: values.length > 0 ? values : undefined });
  };

  const handleStatusChange = (value: string | undefined) => {
    onFiltersChange({
      ...filters,
      status: value as DashboardFilters['status'] | undefined,
    });
  };

  const handleDateRangeChange = (
    dates: [Dayjs | null, Dayjs | null] | null,
  ) => {
    if (dates && dates[0] && dates[1]) {
      onFiltersChange({
        ...filters,
        fromDate: dates[0].format('YYYY-MM-DD'),
        toDate: dates[1].format('YYYY-MM-DD'),
      });
    } else {
      onFiltersChange({
        ...filters,
        fromDate: undefined,
        toDate: undefined,
      });
    }
  };

  // Convert string dates to Dayjs for RangePicker
  const dateRangeValue: [Dayjs, Dayjs] | null =
    filters.fromDate && filters.toDate
      ? [dayjs(filters.fromDate), dayjs(filters.toDate)]
      : null;

  return (
    <Card
      size="small"
      title={
        <Space>
          <FilterOutlined />
          Filtres
          {activeFiltersCount > 0 && (
            <Badge
              count={activeFiltersCount}
              style={{ backgroundColor: token.colorPrimary }}
              data-testid="active-filters-badge"
            />
          )}
        </Space>
      }
      extra={
        <Button
          size="middle"
          icon={<ClearOutlined />}
          onClick={handleReset}
          disabled={activeFiltersCount === 0 || loading}
          data-testid="filter-reset"
        >
          Réinitialiser
        </Button>
      }
      style={{ marginBottom: 16 }}
      data-testid="advanced-filters-panel"
    >
      <Form layout="vertical">
        <Row gutter={16}>
          <Col xs={24} md={8}>
            <Form.Item label="Moteur" style={{ marginBottom: 12 }}>
              <Select
                size="middle"
                style={{ width: '100%' }}
                placeholder="Tous les moteurs"
                allowClear
                value={filters.engine}
                onChange={handleEngineChange}
                options={engineOptions}
                disabled={loading}
                data-testid="filter-engine"
              />
            </Form.Item>
          </Col>
          <Col xs={24} md={8}>
            <Form.Item label="Environnement" style={{ marginBottom: 12 }}>
              <Select
                size="middle"
                style={{ width: '100%' }}
                placeholder="Tous les env."
                allowClear
                value={filters.environment}
                onChange={handleEnvironmentChange}
                options={environmentOptions}
                disabled={loading}
                data-testid="filter-environment"
              />
            </Form.Item>
          </Col>
          <Col xs={24} md={8}>
            <Form.Item label="Tags" style={{ marginBottom: 12 }}>
              <Select
                size="middle"
                style={{ width: '100%' }}
                mode="multiple"
                placeholder="Tous les tags"
                allowClear
                value={filters.tags || []}
                onChange={handleTagsChange}
                options={tagOptions}
                disabled={loading || tagOptions.length === 0}
                maxTagCount={2}
                data-testid="filter-tags"
              />
            </Form.Item>
          </Col>
        </Row>
        <Row gutter={16}>
          <Col xs={24} md={8}>
            <Form.Item label="Statut" style={{ marginBottom: 12 }}>
              <Select
                size="middle"
                style={{ width: '100%' }}
                placeholder="Tous les statuts"
                allowClear
                value={filters.status}
                onChange={handleStatusChange}
                options={DASHBOARD_STATUS_FILTER_OPTIONS}
                disabled={loading}
                data-testid="filter-status"
              />
            </Form.Item>
          </Col>
          <Col xs={24} md={8}>
            <Form.Item label="Période" style={{ marginBottom: 12 }}>
              <RangePicker
                size="middle"
                style={{ width: '100%' }}
                format="DD/MM/YYYY"
                placeholder={['Date début', 'Date fin']}
                value={dateRangeValue || undefined}
                onChange={handleDateRangeChange}
                disabled={loading}
                allowClear
                data-testid="filter-date-range"
              />
            </Form.Item>
          </Col>
        </Row>
      </Form>
    </Card>
  );
}

export default AdvancedFiltersPanel;

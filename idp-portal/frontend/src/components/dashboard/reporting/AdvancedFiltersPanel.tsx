/**
 * AdvancedFiltersPanel - Advanced filter controls for dashboard.
 * Story 8.4, AC1.
 *
 * Displays horizontal filter controls:
 * - Engine (single-select)
 * - Environment (single-select)
 * - Tags (multi-select)
 * - Status (single-select)
 * - Date range picker (from_date / to_date)
 * - Reset button
 * - Active filters count badge
 */

import { Select, DatePicker, Button, Space, Tag } from 'antd';
import { FilterOutlined, ClearOutlined } from '@ant-design/icons';
import type { Dayjs } from 'dayjs';
import dayjs from 'dayjs';
import type { DashboardFilters, FilterOptions } from '../../../types/api';

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

/** Default status options (includes all execution statuses including approval workflow). */
const STATUS_OPTIONS = [
  { label: 'En attente', value: 'PENDING' },
  { label: 'Soumis', value: 'SUBMITTED' },
  { label: 'En cours', value: 'RUNNING' },
  { label: 'Terminé', value: 'COMPLETED' },
  { label: 'Échoué', value: 'FAILED' },
  { label: 'Annulé', value: 'CANCELLED' },
  { label: 'Approbation requise', value: 'PENDING_APPROVAL' },
  { label: 'Rejeté', value: 'REJECTED' },
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
  const activeFiltersCount = countActiveFilters(filters);

  // Build options from API or fallback
  const engineOptions = filterOptions?.engines?.length
    ? filterOptions.engines.map((e) => ({ label: e, value: e }))
    : DEFAULT_ENGINE_OPTIONS;

  const environmentOptions = filterOptions?.environments?.length
    ? filterOptions.environments.map((e) => ({
        label: e.charAt(0).toUpperCase() + e.slice(1),
        value: e,
      }))
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
    <Space wrap size="middle" data-testid="advanced-filters-panel">
      <FilterOutlined style={{ color: '#8c8c8c' }} />

      <Select
        size="middle"
        placeholder="Moteur"
        allowClear
        value={filters.engine}
        onChange={handleEngineChange}
        options={engineOptions}
        style={{ width: 160 }}
        disabled={loading}
        data-testid="filter-engine"
      />

      <Select
        size="middle"
        placeholder="Environnement"
        allowClear
        value={filters.environment}
        onChange={handleEnvironmentChange}
        options={environmentOptions}
        style={{ width: 170 }}
        disabled={loading}
        data-testid="filter-environment"
      />

      <Select
        size="middle"
        mode="multiple"
        placeholder="Tags"
        allowClear
        value={filters.tags || []}
        onChange={handleTagsChange}
        options={tagOptions}
        style={{ minWidth: 170, maxWidth: 300 }}
        disabled={loading || tagOptions.length === 0}
        maxTagCount="responsive"
        data-testid="filter-tags"
      />

      <Select
        size="middle"
        placeholder="Statut"
        allowClear
        value={filters.status}
        onChange={handleStatusChange}
        options={STATUS_OPTIONS}
        style={{ width: 150 }}
        disabled={loading}
        data-testid="filter-status"
      />

      <RangePicker
        size="middle"
        value={dateRangeValue}
        onChange={handleDateRangeChange}
        format="DD/MM/YYYY"
        placeholder={['Date début', 'Date fin']}
        disabled={loading}
        data-testid="filter-date-range"
        style={{ width: 260 }}
      />

      <Button
        size="middle"
        icon={<ClearOutlined />}
        onClick={handleReset}
        disabled={activeFiltersCount === 0 || loading}
        data-testid="filter-reset"
      >
        Réinitialiser
      </Button>

      {activeFiltersCount > 0 && (
        <Tag color="blue" data-testid="active-filters-count">
          {activeFiltersCount} filtre{activeFiltersCount > 1 ? 's' : ''} actif
          {activeFiltersCount > 1 ? 's' : ''}
        </Tag>
      )}
    </Space>
  );
}

export default AdvancedFiltersPanel;

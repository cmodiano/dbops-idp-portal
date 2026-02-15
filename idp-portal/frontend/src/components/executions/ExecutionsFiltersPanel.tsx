/**
 * ExecutionsFiltersPanel - Advanced filters for Executions page (Story 9.10, AC3, AC8).
 *
 * Displays filter controls (apply on change, no Apply button):
 * - Date range (RangePicker with presets)
 * - Action (searchable Select)
 * - Technology/Engine (Select)
 * - Tags (multi-select)
 * - Status (Select)
 * - Environment (Select)
 * - Reset button with active filter count badge
 */

import { useState, useEffect, useCallback } from 'react';
import { Card, Form, Row, Col, DatePicker, Select, Button, Badge, Space, theme } from 'antd';
import { FilterOutlined, ClearOutlined } from '@ant-design/icons';
import type { Dayjs } from 'dayjs';
import dayjs from 'dayjs';
import type { ExecutionFilters } from '../../types/api';
import { fetchExecutionTags } from '../../services/execution_service';
import { fetchCatalogActions, type CatalogAction } from '../../services/catalog_service';
import { useEngines } from '../../hooks/useEngines';
import { useEnvironments } from '../../hooks/useEnvironments';

const { RangePicker } = DatePicker;

/** Status options with French labels. */
const STATUS_OPTIONS = [
  { label: 'Soumise', value: 'SUBMITTED' },
  { label: 'En attente', value: 'PENDING_APPROVAL' },
  { label: 'En cours', value: 'RUNNING' },
  { label: 'Terminée', value: 'COMPLETED' },
  { label: 'Échouée', value: 'FAILED' },
  { label: 'Annulée', value: 'CANCELLED' },
  { label: 'Rejetée', value: 'REJECTED' },
];

// Story 13.7: ENVIRONMENT_OPTIONS removed - use useEnvironments hook instead
// Story 13.7: ENGINE_OPTIONS removed - use useEngines hook instead

/** Date range presets. */
const DATE_PRESETS: { label: string; value: [Dayjs, Dayjs] }[] = [
  { label: '7 derniers jours', value: [dayjs().subtract(7, 'd'), dayjs()] },
  { label: '14 derniers jours', value: [dayjs().subtract(14, 'd'), dayjs()] },
  { label: '30 derniers jours', value: [dayjs().subtract(30, 'd'), dayjs()] },
  { label: '90 derniers jours', value: [dayjs().subtract(90, 'd'), dayjs()] },
];

export interface ExecutionsFiltersPanelProps {
  /** Current filter values (from useExecutionFilters). */
  filters: ExecutionFilters;
  /** Callback when filters are applied. */
  onApplyFilters: (filters: ExecutionFilters) => void;
  /** Callback when filters are reset. */
  onResetFilters: () => void;
  /** Number of active filters (for badge). */
  activeFilterCount: number;
  /** Whether data is loading (disables controls). */
  loading?: boolean;
}

export function ExecutionsFiltersPanel({
  filters,
  onApplyFilters,
  onResetFilters,
  activeFilterCount,
  loading = false,
}: ExecutionsFiltersPanelProps) {
  const { token } = theme.useToken();

  // Story 13.7: Load engines from REF_ENGINES table
  const { engineOptions, loading: enginesLoading } = useEngines();
  // Story 13.7: Load environments from inventory
  const { environmentOptions, loading: environmentsLoading } = useEnvironments();

  // Tags and actions for selects
  const [tags, setTags] = useState<string[]>([]);
  const [tagsLoading, setTagsLoading] = useState(false);
  const [actions, setActions] = useState<CatalogAction[]>([]);
  const [actionsLoading, setActionsLoading] = useState(false);

  const apply = useCallback(
    (newFilters: ExecutionFilters) => {
      onApplyFilters(newFilters);
    },
    [onApplyFilters]
  );

  // Load tags on mount
  useEffect(() => {
    let cancelled = false;
    setTagsLoading(true);
    fetchExecutionTags()
      .then((data) => {
        if (!cancelled) setTags(data);
      })
      .catch(() => {
        if (!cancelled) setTags([]);
      })
      .finally(() => {
        if (!cancelled) setTagsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  // Load actions on mount: use catalog (RBAC) so any user with execution access sees actions they can see
  useEffect(() => {
    let cancelled = false;
    setActionsLoading(true);
    fetchCatalogActions()
      .then((data) => {
        if (!cancelled) setActions(data);
      })
      .catch(() => {
        if (!cancelled) setActions([]);
      })
      .finally(() => {
        if (!cancelled) setActionsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  // Convert date strings to Dayjs for RangePicker
  const dateRangeValue: [Dayjs, Dayjs] | null =
    filters.start_date && filters.end_date
      ? [dayjs(filters.start_date), dayjs(filters.end_date)]
      : null;

  const handleDateRangeChange = (dates: [Dayjs | null, Dayjs | null] | null) => {
    apply({
      ...filters,
      start_date: dates?.[0]?.format('YYYY-MM-DD') || null,
      end_date: dates?.[1]?.format('YYYY-MM-DD') || null,
    });
  };

  const handleReset = () => {
    onResetFilters();
  };

  return (
    <Card
      size="small"
      title={
        <Space>
          <FilterOutlined />
          Filtres avancés
          {activeFilterCount > 0 && (
            <Badge
              count={activeFilterCount}
              style={{ backgroundColor: token.colorPrimary }}
              data-testid="active-filters-badge"
            />
          )}
        </Space>
      }
      style={{ marginBottom: 16 }}
      data-testid="executions-filters-panel"
    >
      <Form layout="vertical">
        {/* Row 1: Date range, Action, Technology */}
        <Row gutter={16}>
          <Col xs={24} md={8}>
            <Form.Item label="Période" style={{ marginBottom: 12 }}>
              <RangePicker
                style={{ width: '100%' }}
                format="DD/MM/YYYY"
                placeholder={['Date début', 'Date fin']}
                presets={DATE_PRESETS}
                value={dateRangeValue}
                onChange={handleDateRangeChange}
                disabled={loading}
                data-testid="filter-date-range"
              />
            </Form.Item>
          </Col>
          <Col xs={24} md={8}>
            <Form.Item label="Action" style={{ marginBottom: 12 }}>
              <Select
                placeholder="Toutes les actions"
                allowClear
                showSearch
                optionFilterProp="label"
                loading={actionsLoading}
                value={filters.action_id}
                onChange={(value) => apply({ ...filters, action_id: value ?? null })}
                options={actions.map((a) => ({ label: a.name, value: a.id }))}
                disabled={loading}
                data-testid="filter-action"
              />
            </Form.Item>
          </Col>
          <Col xs={24} md={8}>
            <Form.Item label="Technologie" style={{ marginBottom: 12 }}>
              <Select
                placeholder="Toutes les technologies"
                allowClear
                value={filters.engine}
                onChange={(value) => apply({ ...filters, engine: value ?? null })}
                options={engineOptions}
                disabled={loading || enginesLoading}
                loading={enginesLoading}
                data-testid="filter-engine"
              />
            </Form.Item>
          </Col>
        </Row>

        {/* Row 2: Tags, Status, Environment, Buttons */}
        <Row gutter={16} align="bottom">
          <Col xs={24} md={6}>
            <Form.Item label="Tags" style={{ marginBottom: 12 }}>
              <Select
                mode="multiple"
                placeholder="Tous les tags"
                allowClear
                maxTagCount={2}
                loading={tagsLoading}
                value={filters.tags ?? []}
                onChange={(value) =>
                  apply({ ...filters, tags: value.length > 0 ? value : null })
                }
                options={tags.map((t) => ({ label: t, value: t }))}
                disabled={loading}
                data-testid="filter-tags"
              />
            </Form.Item>
          </Col>
          <Col xs={24} md={5}>
            <Form.Item label="Statut" style={{ marginBottom: 12 }}>
              <Select
                placeholder="Tous les statuts"
                allowClear
                value={filters.status}
                onChange={(value) => apply({ ...filters, status: value ?? null })}
                options={STATUS_OPTIONS}
                disabled={loading}
                data-testid="filter-status"
              />
            </Form.Item>
          </Col>
          <Col xs={24} md={5}>
            <Form.Item label="Environnement" style={{ marginBottom: 12 }}>
              <Select
                placeholder="Tous les env."
                allowClear
                value={filters.environment}
                onChange={(value) =>
                  apply({ ...filters, environment: value ?? null })
                }
                options={environmentOptions}
                disabled={loading || environmentsLoading}
                loading={environmentsLoading}
                data-testid="filter-environment"
              />
            </Form.Item>
          </Col>
          <Col xs={24} md={8}>
            <Form.Item label=" " style={{ marginBottom: 12 }}>
              <Button
                icon={<ClearOutlined />}
                onClick={handleReset}
                disabled={activeFilterCount === 0 || loading}
                data-testid="filter-reset"
              >
                Réinitialiser
              </Button>
            </Form.Item>
          </Col>
        </Row>
      </Form>
    </Card>
  );
}

export default ExecutionsFiltersPanel;

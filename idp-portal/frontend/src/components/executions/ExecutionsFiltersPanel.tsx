/**
 * ExecutionsFiltersPanel - Advanced filters for Executions page (Story 9.10, AC3, AC8).
 *
 * Displays filter controls:
 * - Date range (RangePicker with presets)
 * - Action (searchable Select)
 * - Technology/Engine (Select)
 * - Tags (multi-select)
 * - Status (Select)
 * - Environment (Select)
 * - Apply/Reset buttons with active filter count badge
 */

import { useState, useEffect } from 'react';
import { Card, Form, Row, Col, DatePicker, Select, Button, Badge, Space, theme } from 'antd';
import { FilterOutlined, ClearOutlined, SearchOutlined } from '@ant-design/icons';
import type { Dayjs } from 'dayjs';
import dayjs from 'dayjs';
import type { ExecutionFilters, ActionListItem } from '../../types/api';
import { fetchExecutionTags } from '../../services/execution_service';
import { listActions } from '../../services/admin_service';

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

/** Environment options. */
const ENVIRONMENT_OPTIONS = [
  { label: 'Développement', value: 'dev' },
  { label: 'Staging', value: 'staging' },
  { label: 'Production', value: 'prod' },
];

/** Technology/Engine options. */
const ENGINE_OPTIONS = [
  { label: 'Oracle', value: 'Oracle' },
  { label: 'SQL Server', value: 'SQL Server' },
  { label: 'DB2', value: 'DB2' },
  { label: 'PostgreSQL', value: 'PostgreSQL' },
  { label: 'MySQL', value: 'MySQL' },
  { label: 'Workflow', value: 'Workflow' },
];

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

  // Local state for form values (before Apply)
  const [localFilters, setLocalFilters] = useState<ExecutionFilters>(filters);

  // Tags and actions for selects
  const [tags, setTags] = useState<string[]>([]);
  const [tagsLoading, setTagsLoading] = useState(false);
  const [actions, setActions] = useState<ActionListItem[]>([]);
  const [actionsLoading, setActionsLoading] = useState(false);

  // Sync local filters when external filters change
  useEffect(() => {
    setLocalFilters(filters);
  }, [filters]);

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

  // Load actions on mount (published only for execution filtering)
  useEffect(() => {
    let cancelled = false;
    setActionsLoading(true);
    listActions('PUBLISHED')
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
    localFilters.start_date && localFilters.end_date
      ? [dayjs(localFilters.start_date), dayjs(localFilters.end_date)]
      : null;

  const handleDateRangeChange = (dates: [Dayjs | null, Dayjs | null] | null) => {
    setLocalFilters({
      ...localFilters,
      start_date: dates?.[0]?.format('YYYY-MM-DD') || null,
      end_date: dates?.[1]?.format('YYYY-MM-DD') || null,
    });
  };

  const handleApply = () => {
    onApplyFilters(localFilters);
  };

  const handleReset = () => {
    setLocalFilters({
      start_date: null,
      end_date: null,
      action_id: null,
      engine: null,
      tags: null,
      status: null,
      environment: null,
    });
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
                value={localFilters.action_id}
                onChange={(value) => setLocalFilters({ ...localFilters, action_id: value ?? null })}
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
                value={localFilters.engine}
                onChange={(value) => setLocalFilters({ ...localFilters, engine: value ?? null })}
                options={ENGINE_OPTIONS}
                disabled={loading}
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
                value={localFilters.tags ?? []}
                onChange={(value) =>
                  setLocalFilters({ ...localFilters, tags: value.length > 0 ? value : null })
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
                value={localFilters.status}
                onChange={(value) => setLocalFilters({ ...localFilters, status: value ?? null })}
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
                value={localFilters.environment}
                onChange={(value) =>
                  setLocalFilters({ ...localFilters, environment: value ?? null })
                }
                options={ENVIRONMENT_OPTIONS}
                disabled={loading}
                data-testid="filter-environment"
              />
            </Form.Item>
          </Col>
          <Col xs={24} md={8}>
            <Form.Item label=" " style={{ marginBottom: 12 }}>
              <Space>
                <Button
                  type="primary"
                  icon={<SearchOutlined />}
                  onClick={handleApply}
                  disabled={loading}
                  data-testid="filter-apply"
                >
                  Appliquer
                </Button>
                <Button
                  icon={<ClearOutlined />}
                  onClick={handleReset}
                  disabled={activeFilterCount === 0 || loading}
                  data-testid="filter-reset"
                >
                  Réinitialiser
                </Button>
              </Space>
            </Form.Item>
          </Col>
        </Row>
      </Form>
    </Card>
  );
}

export default ExecutionsFiltersPanel;

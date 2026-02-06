/**
 * CalendarFiltersPanel - Filters for Calendar page (Story 13.6, AC4, AC5).
 *
 * Displays filter controls aligned with ExecutionsFiltersPanel:
 * - Action (searchable Select)
 * - Environment (Select)
 * - Technology/Engine (Select)
 * - Platform (Select)
 * - Date range (RangePicker, optional)
 * - Reset button with active filter count badge
 */

import { useState, useEffect, useCallback } from 'react';
import { Card, Form, Row, Col, DatePicker, Select, Button, Badge, Space, theme } from 'antd';
import { FilterOutlined, ClearOutlined } from '@ant-design/icons';
import type { Dayjs } from 'dayjs';
import dayjs from 'dayjs';
import type { CalendarFilters } from '../../hooks/useCalendarFilters';
import type { IntegrationResponse } from '../../types/api';
import { getIntegrations } from '../../services/integrations_service';

const { RangePicker } = DatePicker;

/** Environment options. */
const ENVIRONMENT_OPTIONS = [
  { label: 'Développement', value: 'dev' },
  { label: 'Staging', value: 'staging' },
  { label: 'Production', value: 'prod' },
];

/** Technology/Engine options (aligned with ExecutionsFiltersPanel). */
const ENGINE_OPTIONS = [
  { label: 'Oracle', value: 'Oracle' },
  { label: 'SQL Server', value: 'SQL Server' },
  { label: 'DB2', value: 'DB2' },
  { label: 'PostgreSQL', value: 'PostgreSQL' },
  { label: 'MySQL', value: 'MySQL' },
  { label: 'Workflow', value: 'Workflow' },
];

export interface CalendarFiltersPanelProps {
  /** Current filter values (from useCalendarFilters). */
  filters: CalendarFilters;
  /** Callback when filters are applied. */
  onApplyFilters: (filters: CalendarFilters) => void;
  /** Callback when filters are reset. */
  onResetFilters: () => void;
  /** Number of active filters (for badge). */
  activeFilterCount: number;
  /** Whether data is loading (disables controls). */
  loading?: boolean;
  /** Available actions from API response. */
  availableActions?: { action_id: number; action_name: string }[];
}

export function CalendarFiltersPanel({
  filters,
  onApplyFilters,
  onResetFilters,
  activeFilterCount,
  loading = false,
  availableActions = [],
}: CalendarFiltersPanelProps) {
  const { token } = theme.useToken();

  // Platforms for select
  const [integrations, setIntegrations] = useState<IntegrationResponse[]>([]);
  const [integrationsLoading, setIntegrationsLoading] = useState(false);

  const apply = useCallback(
    (newFilters: CalendarFilters) => {
      onApplyFilters(newFilters);
    },
    [onApplyFilters]
  );

  // Load integrations on mount (for platform filter)
  useEffect(() => {
    let cancelled = false;
    setIntegrationsLoading(true);
    getIntegrations()
      .then((data) => {
        if (!cancelled) setIntegrations(data);
      })
      .catch(() => {
        if (!cancelled) setIntegrations([]);
      })
      .finally(() => {
        if (!cancelled) setIntegrationsLoading(false);
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

  // Unique platform types from integrations
  const platformOptions = Array.from(
    new Set(integrations.map((i) => i.type).filter(Boolean))
  ).map((type) => ({ label: type, value: type }));

  return (
    <Card
      size="small"
      title={
        <Space>
          <FilterOutlined />
          Filtres
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
      data-testid="calendar-filters-panel"
    >
      <Form layout="vertical">
        {/* Row 1: Action, Environment, Technology */}
        <Row gutter={16}>
          <Col xs={24} md={8}>
            <Form.Item label="Action" style={{ marginBottom: 12 }}>
              <Select
                placeholder="Toutes les actions"
                allowClear
                showSearch
                optionFilterProp="label"
                value={filters.action_id}
                onChange={(value) => apply({ ...filters, action_id: value ?? null })}
                options={availableActions.map((a) => ({ label: a.action_name, value: a.action_id }))}
                disabled={loading}
                data-testid="filter-action"
              />
            </Form.Item>
          </Col>
          <Col xs={24} md={8}>
            <Form.Item label="Environnement" style={{ marginBottom: 12 }}>
              <Select
                placeholder="Tous les env."
                allowClear
                value={filters.environment}
                onChange={(value) => apply({ ...filters, environment: value ?? null })}
                options={ENVIRONMENT_OPTIONS}
                disabled={loading}
                data-testid="filter-environment"
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
                options={ENGINE_OPTIONS}
                disabled={loading}
                data-testid="filter-engine"
              />
            </Form.Item>
          </Col>
        </Row>

        {/* Row 2: Platform, Date range, Reset */}
        <Row gutter={16} align="bottom">
          <Col xs={24} md={6}>
            <Form.Item label="Plateforme" style={{ marginBottom: 12 }}>
              <Select
                placeholder="Toutes les plateformes"
                allowClear
                loading={integrationsLoading}
                value={filters.platform}
                onChange={(value) => apply({ ...filters, platform: value ?? null })}
                options={platformOptions}
                disabled={loading}
                data-testid="filter-platform"
              />
            </Form.Item>
          </Col>
          <Col xs={24} md={10}>
            <Form.Item label="Période" style={{ marginBottom: 12 }}>
              <RangePicker
                style={{ width: '100%' }}
                format="DD/MM/YYYY"
                placeholder={['Date début', 'Date fin']}
                value={dateRangeValue}
                onChange={handleDateRangeChange}
                disabled={loading}
                data-testid="filter-date-range"
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

export default CalendarFiltersPanel;

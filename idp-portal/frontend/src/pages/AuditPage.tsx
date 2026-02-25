/**
 * AuditPage - Journal d'audit global (Story 6.3, Story 43.3).
 *
 * Story 6.3: AC1 (colonnes table), AC2 (filtres de base), AC3 (drawer détail),
 *            AC4 (tri), AC5 (pagination 50/page), AC8 (accès auditeurs).
 *
 * Story 43.3: AC1 (onglets entity_type), AC2 (Select action_type groupé),
 *             AC3 (Input utilisateur + debounce 300ms), AC4 (intégration API),
 *             AC5 (titre "Journal d'audit"), AC6 (reset pagination),
 *             AC7 (export inclut nouveaux filtres), AC8 (guard drawer non-exécution).
 */

import {
  Typography,
  Input,
  Alert,
  DatePicker,
  Select,
  Space,
  Card,
  Badge,
  Button,
  Dropdown,
  Tooltip,
  Tag,
  Tabs,
} from 'antd';
import type { MenuProps } from 'antd';
import { DownloadOutlined } from '@ant-design/icons';
import dayjs, { type Dayjs } from 'dayjs';
import { useAuth } from '../contexts/AuthContext';
import { useAuditFilters } from '../hooks/useAuditFilters';
import { AuditTable } from '../components/audit/AuditTable';
import { AuditEntryDrawer } from '../components/audit/AuditEntryDrawer';
import { ACTION_TYPE_OPTIONS } from '../constants/auditActionTypes';
import type { AuditStatusFilter } from '../types/api';

const { Title, Text } = Typography;
const { RangePicker } = DatePicker;

const ENVIRONMENT_OPTIONS = [
  { value: 'dev', label: 'DEV' },
  { value: 'staging', label: 'STAGING' },
  { value: 'prod', label: 'PROD' },
];

const STATUS_OPTIONS: { value: AuditStatusFilter; label: string }[] = [
  { value: 'success', label: 'Succès' },
  { value: 'failed', label: 'Échec' },
  { value: 'running', label: 'En cours' },
];

const ENTITY_TYPE_TABS = [
  { key: '', label: 'Tous' },
  { key: 'action', label: 'Actions' },
  { key: 'execution', label: 'Exécutions' },
  { key: 'integration', label: 'Intégrations' },
  { key: 'profile', label: 'Profils' },
  { key: 'user', label: 'Utilisateurs' },
];

const PERIOD_PRESETS: { label: string; value: [Dayjs, Dayjs] }[] = [
  { label: '7 derniers jours', value: [dayjs().subtract(7, 'day'), dayjs()] },
  { label: '30 derniers jours', value: [dayjs().subtract(30, 'day'), dayjs()] },
  { label: '90 derniers jours', value: [dayjs().subtract(90, 'day'), dayjs()] },
];

export default function AuditPage() {
  const { user } = useAuth();
  const {
    topLevelEntries,
    childrenByParentId,
    loading,
    pagination,
    error,
    dateRange,
    setDateRange,
    environment,
    setEnvironment,
    engineType,
    setEngineType,
    actionId,
    setActionId,
    status,
    setStatus,
    correlationId,
    setCorrelationId,
    entityType,
    setEntityType,
    actionType,
    setActionType,
    userSearchInput,
    setUserSearchInput,
    currentPage,
    pageSize,
    sortField,
    sortOrder,
    actions,
    actionsLoading,
    engineOptions,
    enginesLoading,
    drawerOpen,
    selectedEntry,
    selectedExecution,
    selectedSteps,
    drawerLoading,
    drawerError,
    handleRowClick,
    handleDrawerClose,
    handleTableChange,
    exporting,
    handleExport,
  } = useAuditFilters();

  // AC8: contrôle d'accès
  if (!user?.is_auditor) {
    return (
      <div style={{ padding: 24 }}>
        <Title level={2}>Audit</Title>
        <Alert
          type="error"
          title="Accès non autorisé"
          description="Cette page est réservée aux auditeurs."
          showIcon
        />
      </div>
    );
  }

  const exportMenuItems: MenuProps['items'] = [
    {
      key: 'csv',
      label: 'CSV',
      onClick: () => handleExport('csv'),
    },
    {
      key: 'pdf',
      label: 'PDF',
      onClick: () => handleExport('pdf'),
    },
  ];

  return (
    <div style={{ padding: 24 }}>
      <Title level={2}>Journal d'audit</Title>

      {/* Onglets entity_type (AC1) */}
      <Tabs
        activeKey={entityType ?? ''}
        onChange={(key) => setEntityType(key || undefined)}
        items={ENTITY_TYPE_TABS.map((tab) => ({ key: tab.key, label: tab.label }))}
        style={{ marginBottom: 8 }}
      />

      {error && <Alert type="error" title="Erreur" description={error} showIcon style={{ marginBottom: 16 }} />}

      {/* Filters (AC2) */}
      <Card size="small" style={{ marginBottom: 16 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 8 }}>
          <Space wrap>
            <RangePicker
              presets={PERIOD_PRESETS}
              value={dateRange}
              onChange={(dates) => setDateRange(dates || [null, null])}
              placeholder={['Date début', 'Date fin']}
              allowClear
            />
            <Select
              placeholder="Environnement"
              aria-label="Filtre Environnement"
              options={ENVIRONMENT_OPTIONS}
              value={environment}
              onChange={setEnvironment}
              allowClear
              style={{ width: 140 }}
              data-testid="audit-filter-environment"
            />
            <Select
              placeholder="Moteur"
              aria-label="Filtre Moteur (engine_type)"
              options={engineOptions}
              value={engineType}
              onChange={setEngineType}
              allowClear
              style={{ width: 160 }}
              loading={enginesLoading}
              data-testid="audit-filter-engine-type"
            />
            <Select
              placeholder="Action"
              aria-label="Filtre Action"
              options={actions.map((a) => ({ label: a.name, value: a.id }))}
              value={actionId}
              onChange={(v) => setActionId(v ?? undefined)}
              allowClear
              showSearch
              optionFilterProp="label"
              loading={actionsLoading}
              style={{ width: 200 }}
              data-testid="audit-filter-action"
            />
            <Select
              placeholder="Statut"
              options={STATUS_OPTIONS}
              value={status}
              onChange={setStatus}
              allowClear
              style={{ width: 120 }}
            />
            {/* Filtre opération (action_type) — AC2 */}
            <Select
              placeholder="Opération"
              aria-label="Filtre Opération (action_type)"
              options={ACTION_TYPE_OPTIONS}
              value={actionType}
              onChange={(v) => setActionType(v ?? undefined)}
              allowClear
              showSearch
              optionFilterProp="label"
              style={{ width: 220 }}
              data-testid="audit-filter-action-type"
            />
            {/* Recherche utilisateur — AC3 */}
            <Input
              placeholder="Rechercher un utilisateur"
              aria-label="Recherche utilisateur"
              value={userSearchInput}
              onChange={(e) => setUserSearchInput(e.target.value)}
              allowClear
              style={{ width: 200 }}
              data-testid="audit-filter-user-search"
            />
            <Tooltip title="Rechercher toutes les traces d'une exécution par son identifiant de corrélation">
              <Input
                placeholder="Correlation ID"
                value={correlationId}
                onChange={(e) => setCorrelationId(e.target.value)}
                allowClear
                style={{ width: 220 }}
                data-testid="audit-filter-correlation-id"
              />
            </Tooltip>
            {correlationId && (
              <Tag closable onClose={() => setCorrelationId('')} color="blue">
                Correlation: {correlationId}
              </Tag>
            )}
            {pagination && (
              <Badge
                count={pagination.total}
                overflowCount={99999}
                style={{ backgroundColor: '#1890ff' }}
                showZero
              >
                <Text type="secondary" style={{ marginLeft: 8 }}>
                  résultats
                </Text>
              </Badge>
            )}
          </Space>
          {/* Export button — aligned right */}
          <Dropdown menu={{ items: exportMenuItems }} trigger={['click']}>
            <Button icon={<DownloadOutlined />} loading={exporting}>
              Exporter
            </Button>
          </Dropdown>
        </div>
      </Card>

      {/* Table (AC1, AC4, AC5) */}
      <AuditTable
        topLevelEntries={topLevelEntries}
        childrenByParentId={childrenByParentId}
        loading={loading}
        pagination={pagination}
        currentPage={currentPage}
        pageSize={pageSize}
        sortField={sortField}
        sortOrder={sortOrder}
        onChange={handleTableChange}
        onRowClick={handleRowClick}
      />

      {/* Drawer with details (AC3) */}
      <AuditEntryDrawer
        open={drawerOpen}
        entry={selectedEntry}
        execution={selectedExecution}
        steps={selectedSteps}
        loading={drawerLoading}
        error={drawerError}
        onClose={handleDrawerClose}
      />
    </div>
  );
}

/**
 * AuditPage - Journal d'audit global (Story 6.3, Story 43.3, Story 46.7).
 *
 * Story 6.3: AC1 (colonnes table), AC2 (filtres de base), AC3 (drawer détail),
 *            AC4 (tri), AC5 (pagination 50/page), AC8 (accès auditeurs).
 *
 * Story 43.3: AC1 (onglets entity_type), AC2 (Select action_type groupé),
 *             AC3 (Input utilisateur + debounce 300ms), AC4 (intégration API),
 *             AC5 (titre "Journal d'audit"), AC6 (reset pagination),
 *             AC7 (export inclut nouveaux filtres), AC8 (guard drawer non-exécution).
 *
 * Story 46.7: Filtres extraits dans AuditFiltersPanel — harmonisation pattern FilterOutlined.
 */

import { Typography, Alert, Button, Dropdown, Tabs } from 'antd';
import type { MenuProps } from 'antd';
import { DownloadOutlined } from '@ant-design/icons';
import { useAuth } from '../contexts/AuthContext';
import { useAuditFilters } from '../hooks/useAuditFilters';
import { AuditTable } from '../components/audit/AuditTable';
import { AuditEntryDrawer } from '../components/audit/AuditEntryDrawer';
import { AuditFiltersPanel } from '../components/audit/AuditFiltersPanel';

const { Title, Text } = Typography;

const ENTITY_TYPE_TABS = [
  { key: '', label: 'Tous' },
  { key: 'action', label: 'Actions' },
  { key: 'execution', label: 'Exécutions' },
  { key: 'integration', label: 'Intégrations' },
  { key: 'profile', label: 'Profils' },
  { key: 'user', label: 'Utilisateurs' },
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

  // Story 46.7: Nombre de filtres actifs pour le badge
  const activeFilterCount = [
    dateRange[0] !== null || dateRange[1] !== null ? 1 : 0,
    environment ? 1 : 0,
    engineType ? 1 : 0,
    actionId ? 1 : 0,
    status ? 1 : 0,
    correlationId ? 1 : 0,
    actionType ? 1 : 0,
    userSearchInput.trim() ? 1 : 0,
  ].reduce((acc, n) => acc + n, 0);

  // Story 46.7: Reset global de tous les filtres
  const handleResetFilters = () => {
    setDateRange([null, null]);
    setEnvironment(undefined);
    setEngineType(undefined);
    setActionId(undefined);
    setStatus(undefined);
    setCorrelationId('');
    setActionType(undefined);
    setUserSearchInput('');
  };

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
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <Title level={2} style={{ marginBottom: 0 }}>Journal d'audit</Title>
        <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
          {pagination && (
            <Text type="secondary" style={{ whiteSpace: 'nowrap' }}>
              <span style={{ fontWeight: 600, color: '#1890ff', marginRight: 6 }}>{pagination.total}</span>
              résultats
            </Text>
          )}
          {/* Export button (AC7) */}
          <Dropdown menu={{ items: exportMenuItems }} trigger={['click']}>
            <Button icon={<DownloadOutlined />} loading={exporting}>
              Exporter
            </Button>
          </Dropdown>
        </div>
      </div>

      {/* Onglets entity_type (AC1) */}
      <Tabs
        activeKey={entityType ?? ''}
        onChange={(key) => setEntityType(key || undefined)}
        items={ENTITY_TYPE_TABS.map((tab) => ({ key: tab.key, label: tab.label }))}
        style={{ marginBottom: 8 }}
      />

      {error ? <Alert type="error" title="Erreur" description={error} showIcon style={{ marginBottom: 16 }} /> : null}

      {/* Filters — Story 46.7: AuditFiltersPanel (AC2) */}
      <AuditFiltersPanel
        dateRange={dateRange}
        setDateRange={setDateRange}
        environment={environment}
        setEnvironment={setEnvironment}
        engineType={engineType}
        setEngineType={setEngineType}
        actionId={actionId}
        setActionId={setActionId}
        status={status}
        setStatus={setStatus}
        correlationId={correlationId}
        setCorrelationId={setCorrelationId}
        actionType={actionType}
        setActionType={setActionType}
        userSearchInput={userSearchInput}
        setUserSearchInput={setUserSearchInput}
        actions={actions}
        actionsLoading={actionsLoading}
        engineOptions={engineOptions}
        enginesLoading={enginesLoading}
        loading={loading}
        activeFilterCount={activeFilterCount}
        onResetFilters={handleResetFilters}
      />

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

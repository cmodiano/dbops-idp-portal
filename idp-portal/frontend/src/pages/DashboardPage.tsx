/**
 * DashboardPage - Dashboard with statistics and recent activity (Story 5.1).
 *
 * AC1: StatCards with executions_jour, taux_succes_pct, executions_en_cours, executions_en_erreur.
 * AC2: Recent executions table (10 rows, all users visible for DBA).
 * AC3: Click opens drawer with ExecutionTimeline in historical mode.
 * AC5: Layout 2 columns desktop (md), 3 columns large (xl).
 * AC6: Skeleton loading for cards and table.
 */

import { useState, useEffect, useCallback, useMemo } from 'react';
import { Typography, Row, Col, Card, Modal, Skeleton, Alert, Tag, Space } from 'antd';
import {
  PlayCircleOutlined,
  CheckCircleOutlined,
  SyncOutlined,
  CloseCircleOutlined,
  SafetyCertificateOutlined,
} from '@ant-design/icons';
import { StatCard } from '../components/dashboard/StatCard';
import { RecentExecutions } from '../components/dashboard/RecentExecutions';
import { ExecutionsChart } from '../components/dashboard/ExecutionsChart';
import { ExecutionTimeline } from '../components/execution/ExecutionTimeline';
import { PendingApprovalsList } from '../components/dashboard/PendingApprovalsList';
import { fetchStats, fetchRecent, fetchTimeSeries } from '../services/dashboard_service';
import { getIntegrations } from '../services/integrations_service';
import { useDashboardWebSocket } from '../hooks/useDashboardWebSocket';
import { useDashboard } from '../contexts/DashboardContext';
import { getExecution, getExecutionSteps, listPendingApprovals } from '../services/execution_service';
import { useAuth } from '../contexts/AuthContext';
import type {
  DashboardStats,
  DashboardRecentExecution,
  DashboardTimeSeriesPoint,
  ExecutionResponse,
  ExecutionStepResponse,
} from '../types/api';

const { Title } = Typography;

export default function DashboardPage() {
  // Auth context for profile check (Story 7.4)
  const { user } = useAuth();
  const canApprove = user?.profile?.toLowerCase() === 'dba' || user?.profile?.toLowerCase() === 'dbops';

  // Stats state
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [statsLoading, setStatsLoading] = useState(true);
  const [statsError, setStatsError] = useState<string | null>(null);

  // Recent executions state
  const [recent, setRecent] = useState<DashboardRecentExecution[]>([]);
  const [recentLoading, setRecentLoading] = useState(true);
  const [recentError, setRecentError] = useState<string | null>(null);

  // Time series for line chart (last 14 days)
  const [timeSeries, setTimeSeries] = useState<DashboardTimeSeriesPoint[]>([]);
  const [timeSeriesLoading, setTimeSeriesLoading] = useState(true);

  // Integration icons by type (platform/engine) for recent table
  const [integrationIconsByType, setIntegrationIconsByType] = useState<Record<string, string | null>>({});

  // Story 7.4: Pending approvals state (visible only for DBA/DBOPS)
  const [pendingApprovals, setPendingApprovals] = useState<ExecutionResponse[]>([]);
  const [pendingApprovalsLoading, setPendingApprovalsLoading] = useState(false);

  // Execution detail modal state (AC3 — modal for better small-window / logs reading)
  const [modalOpen, setModalOpen] = useState(false);
  const [selectedExecution, setSelectedExecution] = useState<ExecutionResponse | null>(null);
  const [selectedSteps, setSelectedSteps] = useState<ExecutionStepResponse[]>([]);
  const [modalLoading, setModalLoading] = useState(false);
  const [modalError, setModalError] = useState<string | null>(null);

  // Dashboard context for badge management (Story 5.2, AC2, AC3)
  const { addUnseenError, markAllSeen, hasUnseenError } = useDashboard();

  // WebSocket callbacks (Story 5.2, Task 2.3)
  const handleExecutionsUpdate = useCallback((updatedExecutions: DashboardRecentExecution[]) => {
    setRecent(updatedExecutions);
  }, []);

  // Real-time WebSocket updates (Story 5.2, Task 2.3)
  useDashboardWebSocket({
    recentExecutions: recent,
    onExecutionsUpdate: handleExecutionsUpdate,
    onNewError: addUnseenError,
  });

  // Mark errors as seen when page is visited (Story 5.2, AC3)
  useEffect(() => {
    markAllSeen();
  }, [markAllSeen]);

  // Memoize error execution IDs for highlighting (Story 5.2, AC3)
  const errorExecutionIds = useMemo(() => {
    return new Set(
      recent
        .filter((e) => e.status === 'FAILED' && hasUnseenError(e.id))
        .map((e) => e.id)
    );
  }, [recent, hasUnseenError]);

  // Fetch dashboard data
  const loadData = useCallback(async () => {
    // Fetch stats
    setStatsLoading(true);
    setStatsError(null);
    try {
      const data = await fetchStats();
      setStats(data);
    } catch (err) {
      setStatsError(err instanceof Error ? err.message : 'Erreur de chargement');
    } finally {
      setStatsLoading(false);
    }

    // Fetch recent executions
    setRecentLoading(true);
    setRecentError(null);
    try {
      const data = await fetchRecent();
      setRecent(data);
    } catch (err) {
      setRecentError(err instanceof Error ? err.message : 'Erreur de chargement');
    } finally {
      setRecentLoading(false);
    }

    // Fetch time series for line chart
    setTimeSeriesLoading(true);
    try {
      const series = await fetchTimeSeries(14);
      setTimeSeries(series);
    } catch {
      setTimeSeries([]);
    } finally {
      setTimeSeriesLoading(false);
    }

    // Fetch integrations for icons (platform/engine columns); 403 possible for DBA without admin
    try {
      const integrations = await getIntegrations();
      const byType: Record<string, string | null> = {};
      for (const i of integrations) {
        if (i.type && byType[i.type] === undefined) {
          byType[i.type] = i.icon ?? null;
        }
      }
      setIntegrationIconsByType(byType);
    } catch {
      setIntegrationIconsByType({});
    }
  }, []);

  // Story 7.4: Load pending approvals for DBA/DBOPS
  const loadPendingApprovals = useCallback(async () => {
    if (!canApprove) return;
    setPendingApprovalsLoading(true);
    try {
      const response = await listPendingApprovals(50, 0);
      setPendingApprovals(response.data);
    } catch {
      setPendingApprovals([]);
    } finally {
      setPendingApprovalsLoading(false);
    }
  }, [canApprove]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // Story 7.4: Load pending approvals on mount and when canApprove changes
  useEffect(() => {
    loadPendingApprovals();
  }, [loadPendingApprovals]);

  // Story 7.4: Callback after approval/rejection
  const handleApprovalComplete = useCallback(() => {
    loadPendingApprovals();
    loadData(); // Refresh stats and recent executions too
  }, [loadPendingApprovals, loadData]);

  // Open modal with execution details (AC3 — modal + scrollable body for logs in small window)
  const handleRowClick = async (execution: DashboardRecentExecution) => {
    setModalOpen(true);
    setModalLoading(true);
    setModalError(null);
    setSelectedExecution(null);
    setSelectedSteps([]);

    try {
      const [exec, steps] = await Promise.all([
        getExecution(execution.id),
        getExecutionSteps(execution.id),
      ]);
      setSelectedExecution(exec);
      setSelectedSteps(steps);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Erreur de chargement du détail';
      setModalError(message);
    } finally {
      setModalLoading(false);
    }
  };

  return (
    <div style={{ padding: 24 }}>
      <Title level={2}>Dashboard</Title>

      {/* StatCards section (AC1, AC5, AC6): 1 row of 4 on large screens */}
      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        <Col xs={24} sm={12} lg={6} xl={6}>
          <StatCard
            label="Exécutions aujourd'hui"
            value={stats?.executions_jour ?? 0}
            icon={<PlayCircleOutlined />}
            loading={statsLoading}
          />
        </Col>
        <Col xs={24} sm={12} lg={6} xl={6}>
          <StatCard
            label="Taux de succès (24h)"
            value={stats?.taux_succes_pct ?? 0}
            suffix="%"
            icon={<CheckCircleOutlined />}
            variant="success"
            loading={statsLoading}
          />
        </Col>
        <Col xs={24} sm={12} lg={6} xl={6}>
          <StatCard
            label="En cours"
            value={stats?.executions_en_cours ?? 0}
            icon={<SyncOutlined spin={!statsLoading && (stats?.executions_en_cours ?? 0) > 0} />}
            variant="inProgress"
            loading={statsLoading}
          />
        </Col>
        <Col xs={24} sm={12} lg={6} xl={6}>
          <StatCard
            label="En erreur (24h)"
            value={stats?.executions_en_erreur ?? 0}
            icon={<CloseCircleOutlined />}
            variant={(stats?.executions_en_erreur ?? 0) > 0 ? 'error' : 'default'}
            loading={statsLoading}
          />
        </Col>
      </Row>

      {/* Line chart: executions over time (success vs failure) */}
      <ExecutionsChart data={timeSeries} loading={timeSeriesLoading} />

      {/* Story 7.4: Pending approvals section (DBA/DBOPS only) */}
      {canApprove && pendingApprovals.length > 0 && (
        <Card
          title={
            <Space>
              <SafetyCertificateOutlined style={{ color: '#F59E0B' }} />
              <span>Approbations en attente</span>
              <Tag color="warning">{pendingApprovals.length}</Tag>
            </Space>
          }
          style={{ marginBottom: 24, borderColor: '#F59E0B' }}
        >
          <PendingApprovalsList
            executions={pendingApprovals}
            loading={pendingApprovalsLoading}
            onActionComplete={handleApprovalComplete}
          />
        </Card>
      )}

      {statsError && (
        <Alert
          type="error"
          title="Erreur de chargement des statistiques"
          description={statsError}
          showIcon
          style={{ marginBottom: 16 }}
        />
      )}

      {/* Recent executions section (AC2, AC6) — same 24h window as stats so counts match */}
      <Card
        title={
          <div>
            <div>Activité récente</div>
            <Typography.Text type="secondary" style={{ fontSize: 12, fontWeight: 'normal' }}>
              Dernières 24h + toutes les exécutions en cours
            </Typography.Text>
          </div>
        }
        style={{ marginBottom: 24 }}
      >
        {recentError ? (
          <Alert
            type="error"
            title="Erreur de chargement"
            description={recentError}
            showIcon
          />
        ) : (
          <RecentExecutions
            executions={recent}
            loading={recentLoading}
            onRowClick={handleRowClick}
            highlightedIds={errorExecutionIds}
            integrationIconsByType={integrationIconsByType}
          />
        )}
      </Card>

      {/* Execution detail modal (AC3) — scrollable body for logs in small window */}
      <Modal
        title={
          selectedExecution
            ? `Exécution — ${selectedExecution.action_name || `Action #${selectedExecution.action_id}`}`
            : 'Détail exécution'
        }
        open={modalOpen}
        onCancel={() => {
          setModalOpen(false);
          setModalError(null);
        }}
        footer={null}
        width={640}
        destroyOnHidden
        styles={{
          body: {
            maxHeight: '70vh',
            overflowY: 'auto',
          },
        }}
      >
        {modalLoading ? (
          <Skeleton active paragraph={{ rows: 6 }} />
        ) : modalError ? (
          <Alert type="error" title="Erreur de chargement" description={modalError} showIcon />
        ) : selectedExecution ? (
          <ExecutionTimeline
            execution={selectedExecution}
            steps={selectedSteps}
            mode="historical"
          />
        ) : null}
      </Modal>
    </div>
  );
}

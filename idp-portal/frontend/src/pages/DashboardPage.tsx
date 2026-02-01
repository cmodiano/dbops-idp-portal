/**
 * DashboardPage - Reporting dashboard with statistics by technology and environment (Story 8.3).
 *
 * AC1: Dashboard affiche uniquement des statistiques et graphiques (pas de table d'executions recentes).
 * AC2: StatCards with executions_jour, taux_succes_pct, executions_en_cours, executions_en_erreur.
 * AC3: Graphique repartition par technologie.
 * AC4: Graphique repartition par environnement.
 * AC5: Graphique tendances temporelles.
 * AC6: Filtre de periode (7j, 14j, 30j, 90j).
 * AC8: Retrait table recentes, lien vers /executions.
 *
 * Story 7.4: PendingApprovalsList still shown for DBA/DBOPS if there are pending approvals.
 */

import { useState, useEffect, useCallback } from 'react';
import { Typography, Card, Tag, Space } from 'antd';
import { SafetyCertificateOutlined } from '@ant-design/icons';
import { ReportingDashboard } from '../components/dashboard/reporting';
import { PendingApprovalsList } from '../components/dashboard/PendingApprovalsList';
import { listPendingApprovals } from '../services/execution_service';
import { useAuth } from '../contexts/AuthContext';
import type { ExecutionResponse } from '../types/api';

const { Title } = Typography;

export default function DashboardPage() {
  // Auth context for profile check (Story 7.4)
  const { user } = useAuth();
  const canApprove = user?.profile?.toLowerCase() === 'dba' || user?.profile?.toLowerCase() === 'dbops';

  // Story 7.4: Pending approvals state (visible only for DBA/DBOPS)
  const [pendingApprovals, setPendingApprovals] = useState<ExecutionResponse[]>([]);
  const [pendingApprovalsLoading, setPendingApprovalsLoading] = useState(false);

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

  // Story 7.4: Load pending approvals on mount and when canApprove changes
  useEffect(() => {
    loadPendingApprovals();
  }, [loadPendingApprovals]);

  // Story 7.4: Callback after approval/rejection
  const handleApprovalComplete = useCallback(() => {
    loadPendingApprovals();
  }, [loadPendingApprovals]);

  return (
    <div style={{ padding: 24 }}>
      <Title level={2}>Dashboard</Title>

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

      {/* Story 8.3: Reporting dashboard with statistics and charts */}
      <ReportingDashboard />
    </div>
  );
}

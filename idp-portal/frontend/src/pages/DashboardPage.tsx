/**
 * AnalyticsPage (formerly DashboardPage) - Advanced analytics with statistics by technology and environment.
 * Story 8.3, Story 9.10 (rename to Analytics + RBAC DBOPS only).
 *
 * AC3: Graphique repartition par technologie.
 * AC4: Graphique repartition par environnement.
 * AC5: Graphique tendances temporelles.
 * AC6: Filtre de periode (7j, 14j, 30j, 90j).
 * AC8: Link to /executions.
 *
 * Story 9.4: StatCards moved to ExecutionsPage.
 * Story 9.10: Renamed to Analytics, restricted to DBOPS only.
 */

import { Typography } from 'antd';
import { useState } from 'react';
import { ReportingDashboard } from '../components/dashboard/reporting/ReportingDashboard';
import { useDashboardWebSocket } from '../hooks/useDashboardWebSocket';
import type { DashboardRecentExecution } from '../types/api';

const { Title } = Typography;

export default function DashboardPage() {
  const [recentExecutions, setRecentExecutions] = useState<DashboardRecentExecution[]>([]);

  useDashboardWebSocket({
    recentExecutions,
    onExecutionsUpdate: setRecentExecutions,
  });

  return (
    <div style={{ padding: 24 }}>
      {/* Story 9.10: Renamed from Dashboard to Analytics */}
      <Title level={2}>Statistiques</Title>

      {/* Story 8.3: Reporting dashboard with statistics and charts */}
      {/* Story 9.4: StatCards moved to ExecutionsPage */}
      <ReportingDashboard />
    </div>
  );
}

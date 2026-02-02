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
 * Story 8.8 AC3: PendingApprovalsList removed - moved to ExecutionsPage.
 */

import { Typography } from 'antd';
import { ReportingDashboard } from '../components/dashboard/reporting';

const { Title } = Typography;

export default function DashboardPage() {
  return (
    <div style={{ padding: 24 }}>
      <Title level={2}>Dashboard</Title>

      {/* Story 8.3: Reporting dashboard with statistics and charts */}
      {/* Story 8.8 AC3: PendingApprovalsList moved to ExecutionsPage */}
      <ReportingDashboard />
    </div>
  );
}

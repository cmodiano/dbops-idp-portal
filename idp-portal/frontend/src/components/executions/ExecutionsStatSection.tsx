/**
 * ExecutionsStatSection - StatCards + TrendLineChart section
 *
 * Story 26.4 - AC4: Extracted from ExecutionsPage.tsx.
 * Story 9.4: 4 StatCards (executions du jour, taux de succès, en cours, en erreur).
 * Story 9.10: TrendLineChart under StatCards.
 */
import { Row, Col } from 'antd';
import {
  RocketOutlined,
  CheckCircleOutlined,
  SyncOutlined,
  ExclamationCircleOutlined,
} from '@ant-design/icons';
import { StatCard } from '../dashboard/StatCard';
import { TrendLineChart } from '../dashboard/reporting/TrendLineChart';
import type {
  DashboardStats,
  DashboardTimeSeriesPoint,
  ExecutionFilters,
} from '../../types/api';

export interface ExecutionsStatSectionProps {
  statsData: DashboardStats | null;
  statsLoading: boolean;
  timeSeriesData: DashboardTimeSeriesPoint[];
  timeSeriesLoading: boolean;
  filters: ExecutionFilters;
}

export const ExecutionsStatSection: React.FC<ExecutionsStatSectionProps> = ({
  statsData,
  statsLoading,
  timeSeriesData,
  timeSeriesLoading,
  filters,
}) => (
  <>
    {/* Story 9.4 AC1, AC3, AC4, AC5; Story 9.10 AC6: StatCards section (filter-aware) */}
    <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
      <Col xs={24} sm={12} md={6}>
        <StatCard
          label={filters.start_date || filters.end_date ? "Exécutions" : "Exécutions du jour"}
          value={statsData?.executions_jour ?? 0}
          icon={<RocketOutlined />}
          loading={statsLoading}
        />
      </Col>
      <Col xs={24} sm={12} md={6}>
        <StatCard
          label="Taux de succès"
          value={statsData?.taux_succes_pct ?? 0}
          suffix="%"
          icon={<CheckCircleOutlined />}
          variant="success"
          loading={statsLoading}
        />
      </Col>
      <Col xs={24} sm={12} md={6}>
        <StatCard
          label="En cours"
          value={statsData?.executions_en_cours ?? 0}
          icon={<SyncOutlined spin={!statsLoading && (statsData?.executions_en_cours ?? 0) > 0} />}
          variant="inProgress"
          loading={statsLoading}
        />
      </Col>
      <Col xs={24} sm={12} md={6}>
        <StatCard
          label="En erreur"
          value={statsData?.executions_en_erreur ?? 0}
          icon={<ExclamationCircleOutlined />}
          variant="error"
          loading={statsLoading}
        />
      </Col>
    </Row>

    {/* Story 9.10 AC2, AC5: TrendLineChart (filter-aware) */}
    <div style={{ marginBottom: 16 }}>
      <TrendLineChart data={timeSeriesData} loading={timeSeriesLoading} />
    </div>
  </>
);

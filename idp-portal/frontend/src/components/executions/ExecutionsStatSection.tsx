/**
 * ExecutionsStatSection - StatCards + TrendLineChart section
 *
 * Story 26.4 - AC4: Extracted from ExecutionsPage.tsx.
 * Story 9.4: 4 StatCards (executions du jour, taux de succès, en cours, en erreur).
 * Story 9.10: TrendLineChart under StatCards.
 * Story 60.11: Avg execution time StatCard + analytics link.
 */
import { Row, Col, Typography } from 'antd';
import {
  RocketOutlined,
  CheckCircleOutlined,
  SyncOutlined,
  ExclamationCircleOutlined,
  ClockCircleOutlined,
  ArrowRightOutlined,
} from '@ant-design/icons';
import { Link } from 'react-router';
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
  avgExecutionTimeS?: number | null;
  avgExecutionTimeLoading?: boolean;
}

export const ExecutionsStatSection: React.FC<ExecutionsStatSectionProps> = ({
  statsData,
  statsLoading,
  timeSeriesData,
  timeSeriesLoading,
  filters,
  avgExecutionTimeS,
  avgExecutionTimeLoading,
}) => {
  const avgTimeValue: number | string =
    avgExecutionTimeS !== null && avgExecutionTimeS !== undefined
      ? avgExecutionTimeS
      : 'N/D';
  const avgTimeSuffix = typeof avgTimeValue === 'number' ? 's' : undefined;

  return (
    <>
      {/* Story 9.4 AC1, AC3, AC4, AC5; Story 9.10 AC6: StatCards section (filter-aware) */}
      <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
        <Col xs={24} sm={12} md={6}>
          <StatCard
            label={filters.start_date || filters.end_date ? "Exécutions" : "Exécutions du jour"}
            value={statsData?.executions_jour ?? 0}
            icon={<RocketOutlined />}
            loading={statsLoading}
            tooltip="Nombre d'exécutions soumises ou démarrées aujourd'hui (depuis minuit)"
            zeroText="Aucune pour l'instant"
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
            tooltip="Pourcentage d'exécutions terminées avec succès sur la période"
          />
        </Col>
        <Col xs={24} sm={12} md={6}>
          <StatCard
            label="En cours"
            value={statsData?.executions_en_cours ?? 0}
            icon={<SyncOutlined spin={!statsLoading && (statsData?.executions_en_cours ?? 0) > 0} />}
            variant="inProgress"
            loading={statsLoading}
            tooltip="Exécutions actuellement en cours d'exécution"
          />
        </Col>
        <Col xs={24} sm={12} md={6}>
          <StatCard
            label="En erreur"
            value={statsData?.executions_en_erreur ?? 0}
            icon={<ExclamationCircleOutlined />}
            variant="error"
            loading={statsLoading}
            tooltip="Exécutions terminées avec erreur (période filtrée ou aujourd'hui)"
          />
        </Col>
      </Row>

      {/* Story 9.10 AC2, AC5: TrendLineChart (filter-aware) */}
      <div style={{ marginBottom: 16 }}>
        <TrendLineChart data={timeSeriesData} loading={timeSeriesLoading} />
      </div>

      {/* Story 60.11: Durée moy. d'exéc. + lien analytics */}
      {avgExecutionTimeS !== undefined && (
        <Row gutter={[16, 16]} align="middle" style={{ marginTop: 8 }}>
          <Col xs={24} sm={12} md={6}>
            <StatCard
              label="Durée moy. d'exéc."
              value={avgTimeValue}
              suffix={avgTimeSuffix}
              icon={<ClockCircleOutlined />}
              variant="inProgress"
              loading={avgExecutionTimeLoading ?? false}
              tooltip="Durée moyenne des exécutions COMPLETED sur la période"
            />
          </Col>
          <Col xs={24} sm={12} md={18} style={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end' }}>
            <Link to="/analytics">
              <Typography.Text type="secondary">
                Voir les statistiques détaillées <ArrowRightOutlined />
              </Typography.Text>
            </Link>
          </Col>
        </Row>
      )}
    </>
  );
};

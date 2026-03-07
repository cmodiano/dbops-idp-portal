/**
 * OperationsActivitySection — Section "Activité opérationnelle" (Story 60.9).
 *
 * Displays 3 StatCards from 3 parallel API calls:
 * - "Durée moy. d'exéc." : avg_execution_time_s (null → "N/D")
 * - "Approuvées" : approved_count with approval_rate in tooltip
 * - "Planifiées" : scheduled_count
 *
 * Uses Promise.allSettled so a failure on one endpoint does not block the others.
 * Errors other than 403 display an Alert.
 * Loading state shows Skeleton inside each StatCard.
 */

import { useState, useEffect } from 'react';
import { Row, Col, Alert, Typography, Divider } from 'antd';
import { StatCard } from '../StatCard';
import { TopActionsByExecutionChart } from './TopActionsByExecutionChart';
import { TopActionsByFailureChart } from './TopActionsByFailureChart';
import { ApprobationsRatioChart } from './ApprobationsRatioChart';
import {
  fetchStatsOperations,
  fetchStatsApprobations,
  fetchStatsPlanifiees,
} from '../../../services/dashboard_service';
import type {
  DashboardFilters,
  StatsOperationsData,
  StatsApprobationsData,
  StatsPlanifieesData,
} from '../../../types/api';

const { Title } = Typography;

export interface OperationsActivitySectionProps {
  filters: DashboardFilters;
}

export function OperationsActivitySection({ filters }: OperationsActivitySectionProps) {
  const [operationsData, setOperationsData] = useState<StatsOperationsData | null>(null);
  const [approbationsData, setApprobationsData] = useState<StatsApprobationsData | null>(null);
  const [planifieesData, setPlanifieesData] = useState<StatsPlanifieesData | null>(null);
  const [sectionLoading, setSectionLoading] = useState(true);
  const [sectionError, setSectionError] = useState<string | null>(null);

  // Use JSON.stringify as dependency to avoid infinite re-renders (filters object re-created on each render)
  const filtersKey = JSON.stringify(filters);

  useEffect(() => {
    let cancelled = false;

    async function loadData() {
      setSectionLoading(true);
      setSectionError(null);

      const [operationsResult, approbationsResult, planifieesResult] = await Promise.allSettled([
        fetchStatsOperations(filters),
        fetchStatsApprobations(filters),
        fetchStatsPlanifiees(filters),
      ]);

      if (cancelled) return;

      if (operationsResult.status === 'fulfilled') {
        setOperationsData(operationsResult.value);
      } else {
        const err = operationsResult.reason;
        setSectionError(err instanceof Error ? err.message : 'Erreur de chargement');
      }

      if (approbationsResult.status === 'fulfilled') {
        setApprobationsData(approbationsResult.value);
      } else {
        const err = approbationsResult.reason;
        setSectionError((prev) => prev ?? (err instanceof Error ? err.message : 'Erreur de chargement'));
      }

      if (planifieesResult.status === 'fulfilled') {
        setPlanifieesData(planifieesResult.value);
      } else {
        const err = planifieesResult.reason;
        setSectionError((prev) => prev ?? (err instanceof Error ? err.message : 'Erreur de chargement'));
      }

      setSectionLoading(false);
    }

    loadData();

    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filtersKey]);

  const avgTime = operationsData?.avg_execution_time_s;
  const avgTimeValue: number | string =
    avgTime !== null && avgTime !== undefined ? avgTime : 'N/D';
  const avgTimeSuffix = typeof avgTimeValue === 'number' ? 's' : undefined;

  const approvedCount = approbationsData?.approved_count ?? 0;
  const approvalRate = approbationsData?.approval_rate;
  const approvalTooltip = `Exécutions approuvées sur la période (taux : ${
    approvalRate !== null && approvalRate !== undefined
      ? approvalRate.toFixed(1) + ' %'
      : 'N/D'
  })`;

  const scheduledCount = planifieesData?.scheduled_count ?? 0;

  return (
    <>
      <Divider />
      <Title level={5}>Activité opérationnelle</Title>

      {sectionError && (
        <Alert
          type="error"
          title={sectionError}
          showIcon
          closable
          onClose={() => setSectionError(null)}
        />
      )}

      <Row gutter={[16, 16]}>
        <Col xs={24} sm={8}>
          <StatCard
            label="Durée moy. d'exéc."
            value={avgTimeValue}
            suffix={avgTimeSuffix}
            variant="inProgress"
            tooltip="Durée moyenne des exécutions COMPLETED sur la période"
            loading={sectionLoading}
          />
        </Col>
        <Col xs={24} sm={8}>
          <StatCard
            label="Approuvées"
            value={approvedCount}
            variant="success"
            tooltip={approvalTooltip}
            loading={sectionLoading}
          />
        </Col>
        <Col xs={24} sm={8}>
          <StatCard
            label="Planifiées"
            value={scheduledCount}
            variant="default"
            tooltip="Exécutions déclenchées par une planification sur la période"
            loading={sectionLoading}
          />
        </Col>
      </Row>

      {/* Graphiques opérations (Story 60.10) */}
      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col xs={24} md={12}>
          <TopActionsByExecutionChart
            data={operationsData?.top_actions_by_execution.slice(0, 5) ?? []}
            loading={sectionLoading}
          />
        </Col>
        <Col xs={24} md={12}>
          <TopActionsByFailureChart
            data={operationsData?.top_actions_by_failure.slice(0, 5) ?? []}
            loading={sectionLoading}
          />
        </Col>
      </Row>

      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col xs={24}>
          <ApprobationsRatioChart
            approved={approbationsData?.approved_count ?? 0}
            rejected={approbationsData?.rejected_count ?? 0}
            approvalRate={approbationsData?.approval_rate ?? null}
            loading={sectionLoading}
          />
        </Col>
      </Row>
    </>
  );
}

export default OperationsActivitySection;

/**
 * AdminAnalyticsDashboard - Main analytics dashboard for DBOPS admin.
 * Story 8.2, AC1, AC2, AC3, Task 10.
 *
 * Features:
 * - StatCard for total published actions
 * - Period selector (30j, 90j, 12 mois)
 * - EngineBarChart and ProfileBarChart in 2-column grid
 * - AdoptionTrendChart full-width
 */

import { useState, useEffect, useCallback } from 'react';
import { Row, Col, Statistic, Card, Segmented, Alert, Skeleton, App } from 'antd';
import { FileTextOutlined } from '@ant-design/icons';
import { EngineBarChart } from './EngineBarChart';
import { ProfileBarChart } from './ProfileBarChart';
import { AdoptionTrendChart } from './AdoptionTrendChart';
import { fetchAdminAnalytics } from '../../../services/admin_service';
import type { AdminAnalytics } from '../../../types/api';

/** Period options for the selector. */
const periodOptions = [
  { label: '30 jours', value: 30 },
  { label: '90 jours', value: 90 },
  { label: '12 mois', value: 365 },
];

export function AdminAnalyticsDashboard() {
  const { notification } = App.useApp();
  const [period, setPeriod] = useState<number>(90);
  const [data, setData] = useState<AdminAnalytics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadData = useCallback(async (days: number) => {
    setLoading(true);
    setError(null);
    try {
      const analytics = await fetchAdminAnalytics(days);
      setData(analytics);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Erreur de chargement des metriques';
      setError(message);
      notification.error({ message: 'Erreur', description: message });
    } finally {
      setLoading(false);
    }
  }, [notification]);

  useEffect(() => {
    loadData(period);
  }, [period, loadData]);

  const handlePeriodChange = (value: number | string) => {
    setPeriod(value as number);
  };

  if (error && !data) {
    return (
      <Alert
        type="error"
        message="Erreur"
        description={error}
        showIcon
        style={{ marginTop: 16 }}
      />
    );
  }

  return (
    <div style={{ padding: '16px 0' }}>
      {/* Header: StatCard + Period Selector */}
      <Row gutter={[16, 16]} align="middle" style={{ marginBottom: 24 }}>
        <Col xs={24} sm={12} md={8}>
          <Card size="small">
            {loading ? (
              <Skeleton.Input active size="large" style={{ width: 120 }} />
            ) : (
              <Statistic
                title="Actions publiees"
                value={data?.total_published_actions ?? 0}
                prefix={<FileTextOutlined />}
                styles={{ content: { color: '#3B82F6' } }}
              />
            )}
          </Card>
        </Col>
        <Col xs={24} sm={12} md={16} style={{ textAlign: 'right' }}>
          <Segmented
            options={periodOptions}
            value={period}
            onChange={handlePeriodChange}
            disabled={loading}
          />
        </Col>
      </Row>

      {/* Bar Charts: 2-column grid */}
      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        <Col xs={24} md={12}>
          <EngineBarChart
            data={data?.executions_by_engine ?? []}
            loading={loading}
          />
        </Col>
        <Col xs={24} md={12}>
          <ProfileBarChart
            data={data?.executions_by_profile ?? []}
            loading={loading}
          />
        </Col>
      </Row>

      {/* Trend Chart: full-width */}
      <Row gutter={[16, 16]}>
        <Col span={24}>
          <AdoptionTrendChart
            data={data?.adoption_trend ?? []}
            loading={loading}
          />
        </Col>
      </Row>
    </div>
  );
}

export default AdminAnalyticsDashboard;

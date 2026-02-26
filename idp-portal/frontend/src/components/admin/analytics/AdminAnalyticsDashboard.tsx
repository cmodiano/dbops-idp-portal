/**
 * AdminAnalyticsDashboard - Main analytics dashboard for DBOPS admin.
 * Story 8.2, AC1, AC2, AC3, Task 10.
 *
 * Features:
 * - StatCard for total published actions
 * - Period selector (30j, 90j, 12 mois)
 * - EngineBarChart and ProfileBarChart in 2-column grid
 * - AdoptionTrendChart full-width
 *
 * Story 48.8 (SOLID-FE-4, AC2): fetchAdminAnalytics encapsulé dans useAdminAnalytics hook (DIP).
 */

import { useState, useEffect } from 'react';
import { Row, Col, Statistic, Card, Segmented, Alert, Skeleton, App } from 'antd';
import { FileTextOutlined } from '@ant-design/icons';
import { EngineBarChart } from './EngineBarChart';
import { ProfileBarChart } from './ProfileBarChart';
import { AdoptionTrendChart } from './AdoptionTrendChart';
import { useAdminAnalytics } from '../../../hooks/useAdminAnalytics';

/** Period options for the selector. */
const periodOptions = [
  { label: '30 jours', value: 30 },
  { label: '90 jours', value: 90 },
  { label: '12 mois', value: 365 },
];

export function AdminAnalyticsDashboard() {
  const { notification } = App.useApp();
  const [period, setPeriod] = useState<number>(90);
  const { data, loading, error } = useAdminAnalytics(period);

  useEffect(() => {
    if (error) notification.error({ title: 'Erreur', description: error });
  }, [error, notification]);

  const handlePeriodChange = (value: number | string) => {
    setPeriod(value as number);
  };

  if (error && !data) {
    return (
      <Alert
        type="error"
        title="Erreur"
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
                title="Actions publiées"
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

import { lazy, Suspense } from 'react';
import { Card, Spin } from 'antd';

const AdminAnalyticsDashboard = lazy(() => import('../../components/admin/analytics/AdminAnalyticsDashboard'));

export function MetricsAdminPanel() {
  return (
    <Card styles={{ header: { borderBottom: 'none', paddingBottom: 0 }, body: { paddingTop: 16 } }}>
      <Suspense fallback={<Spin style={{ display: 'block', margin: '48px auto' }} />}>
        <AdminAnalyticsDashboard />
      </Suspense>
    </Card>
  );
}

import { lazy, Suspense } from 'react';
import { Card, Spin } from 'antd';

const FeatureFlagsPanel = lazy(() => import('../../components/admin/FeatureFlagsPanel').then(m => ({ default: m.FeatureFlagsPanel })));

export function FeatureFlagsAdminPanel() {
  return (
    <Card styles={{ header: { borderBottom: 'none', paddingBottom: 0 }, body: { paddingTop: 16 } }}>
      <Suspense fallback={<Spin style={{ display: 'block', margin: '48px auto' }} />}>
        <FeatureFlagsPanel />
      </Suspense>
    </Card>
  );
}

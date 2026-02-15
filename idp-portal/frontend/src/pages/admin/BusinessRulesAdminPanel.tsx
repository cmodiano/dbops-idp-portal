/**
 * Story 28.4, AC#1: Wrapper pour l'onglet Admin "R\u00e8gles m\u00e9tier".
 */

import { lazy, Suspense } from 'react';
import { Card, Spin } from 'antd';

const BusinessRulesPolicyPanel = lazy(() =>
  import('../../components/admin/BusinessRulesPolicyPanel').then(m => ({ default: m.BusinessRulesPolicyPanel })),
);

export function BusinessRulesAdminPanel() {
  return (
    <Card styles={{ header: { borderBottom: 'none', paddingBottom: 0 }, body: { paddingTop: 16 } }}>
      <Suspense fallback={<Spin style={{ display: 'block', margin: '48px auto' }} />}>
        <BusinessRulesPolicyPanel />
      </Suspense>
    </Card>
  );
}

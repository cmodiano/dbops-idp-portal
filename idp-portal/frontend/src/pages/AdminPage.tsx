/**
 * AdminPage - Administration du Catalogue.
 *
 * Orchestrateur léger qui délègue chaque onglet à un sous-composant dédié.
 * Voir pages/admin/ pour les panels individuels.
 */

import { Typography, Tabs, App } from 'antd';
import { useTheme } from '../contexts/ThemeContext';
import {
  ActionsAdminPanel,
  ProfilesAdminPanel,
  IntegrationsAdminPanel,
  BusinessRulesAdminPanel,
  CategoriesAdminPanel,
  MetricsAdminPanel,
  FeatureFlagsAdminPanel,
} from './admin';

const { Title } = Typography;

export default function AdminPage() {
  const { notification, modal } = App.useApp();
  const { effectiveMode } = useTheme();

  return (
    <div style={{ maxWidth: 1400, margin: '0 auto' }}>
      {/* Page Header */}
      <div style={{ marginBottom: 32 }}>
        <Title level={2} style={{ margin: 0, marginBottom: 8 }}>
          Administration du Catalogue
        </Title>
        <Typography.Text type="secondary">
          Gérez vos actions et profils
        </Typography.Text>
      </div>

      <Tabs
        defaultActiveKey="actions"
        destroyOnHidden
        items={[
          {
            key: 'actions',
            label: 'Actions',
            children: <ActionsAdminPanel notification={notification} modal={modal} isDark={effectiveMode === 'dark'} />,
          },
          {
            key: 'profiles',
            label: 'Profils',
            children: <ProfilesAdminPanel notification={notification} />,
          },
          {
            key: 'integrations',
            label: 'Intégrations',
            children: <IntegrationsAdminPanel notification={notification} />,
          },
          {
            key: 'business-rules',
            label: 'Règles métier',
            children: <BusinessRulesAdminPanel />,
          },
          {
            key: 'categories',
            label: 'Catégories',
            children: <CategoriesAdminPanel />,
          },
          {
            key: 'analytics',
            label: 'Métriques',
            children: <MetricsAdminPanel />,
          },
          {
            key: 'feature-flags',
            label: 'Feature Flags',
            children: <FeatureFlagsAdminPanel />,
          },
        ]}
      />
    </div>
  );
}

/**
 * AdminPage - Administration du Catalogue.
 *
 * Orchestrateur léger qui délègue chaque onglet à un sous-composant dédié.
 * Voir pages/admin/ pour les panels individuels.
 */

import { Typography, Tabs, App } from 'antd';
import {
  AppstoreOutlined,
  TeamOutlined,
  ApiOutlined,
  AuditOutlined,
  TagsOutlined,
  ToolOutlined,
  BarChartOutlined,
  ExperimentOutlined,
} from '@ant-design/icons';
import { useTheme } from '../contexts/ThemeContext';
import {
  ActionsAdminPanel,
  ProfilesAdminPanel,
  IntegrationsAdminPanel,
  BusinessRulesAdminPanel,
  CategoriesAdminPanel,
  EnginesAdminPanel,
  MetricsAdminPanel,
  FeatureFlagsAdminPanel,
} from './admin';

const { Title } = Typography;

export default function AdminPage() {
  const { notification, modal } = App.useApp();
  const { effectiveMode } = useTheme();

  return (
    <div style={{ width: '100%' }}>
      {/* Page Header */}
      <div style={{ marginBottom: 32 }}>
        <Title level={2} style={{ margin: 0, marginBottom: 8 }}>
          Administration du Catalogue
        </Title>
        <Typography.Text type="secondary">
          Gérez les actions, profils, intégrations, règles métier et configurations du portail
        </Typography.Text>
      </div>

      <Tabs
        defaultActiveKey="actions"
        destroyOnHidden
        size="large"
        tabBarStyle={{ marginBottom: 24 }}
        items={[
          {
            key: 'actions',
            label: 'Actions',
            icon: <AppstoreOutlined />,
            children: <ActionsAdminPanel notification={notification} modal={modal} isDark={effectiveMode === 'dark'} />,
          },
          {
            key: 'profiles',
            label: 'Profils',
            icon: <TeamOutlined />,
            children: <ProfilesAdminPanel notification={notification} />,
          },
          {
            key: 'integrations',
            label: 'Intégrations',
            icon: <ApiOutlined />,
            children: <IntegrationsAdminPanel notification={notification} />,
          },
          {
            key: 'business-rules',
            label: 'Règles métier',
            icon: <AuditOutlined />,
            children: <BusinessRulesAdminPanel />,
          },
          {
            key: 'categories',
            label: 'Catégories',
            icon: <TagsOutlined />,
            children: <CategoriesAdminPanel />,
          },
          {
            key: 'engines',
            label: 'Moteurs',
            icon: <ToolOutlined />,
            children: <EnginesAdminPanel />,
          },
          {
            key: 'analytics',
            label: 'Métriques',
            icon: <BarChartOutlined />,
            children: <MetricsAdminPanel />,
          },
          {
            key: 'feature-flags',
            label: 'Feature Flags',
            icon: <ExperimentOutlined />,
            children: <FeatureFlagsAdminPanel />,
          },
        ]}
      />
    </div>
  );
}

import './TopNav.css';
import { Tabs, Dropdown, Avatar, Space, Typography } from 'antd';
import {
  AppstoreOutlined,
  PlayCircleOutlined,
  DashboardOutlined,
  SettingOutlined,
  LogoutOutlined,
  UserOutlined,
} from '@ant-design/icons';
import { useNavigate, useLocation } from 'react-router';
import { useAuth } from '../../contexts/AuthContext';
import type { NavigationTabKey } from '../../types/common';
import type { MenuProps } from 'antd';

const { Text } = Typography;

const TAB_CONFIG: Record<NavigationTabKey, { label: string; icon: React.ReactNode }> = {
  catalog: { label: 'Catalogue', icon: <AppstoreOutlined /> },
  executions: { label: 'Executions', icon: <PlayCircleOutlined /> },
  dashboard: { label: 'Dashboard', icon: <DashboardOutlined /> },
  admin: { label: 'Admin', icon: <SettingOutlined /> },
};

const TAB_ROUTES: Record<NavigationTabKey, string> = {
  catalog: '/catalog',
  executions: '/executions',
  dashboard: '/dashboard',
  admin: '/admin',
};

export function TopNav() {
  const navigate = useNavigate();
  const location = useLocation();
  const { user, logout } = useAuth();

  const navigationTabs = user?.navigation_tabs ?? [];

  const tabItems = navigationTabs.map((key) => ({
    key,
    label: (
      <span>
        {TAB_CONFIG[key]?.icon} {TAB_CONFIG[key]?.label ?? key}
      </span>
    ),
  }));

  const activeKey = navigationTabs.find((key) =>
    location.pathname.startsWith(TAB_ROUTES[key]),
  );

  const handleTabChange = (key: string) => {
    const route = TAB_ROUTES[key as NavigationTabKey];
    if (route) navigate(route);
  };

  // Profile dropdown menu items
  const profileMenuItems: MenuProps['items'] = [
    {
      key: 'name',
      label: <Text strong>{user?.display_name ?? user?.username ?? ''}</Text>,
      disabled: true,
    },
    {
      key: 'role',
      label: <Text type="secondary">{user?.profile ?? ''}</Text>,
      disabled: true,
    },
    { type: 'divider' },
    {
      key: 'logout',
      label: 'Deconnexion',
      icon: <LogoutOutlined />,
      danger: true,
      onClick: () => logout(),
    },
  ];

  const avatarLetter = user?.display_name?.[0] ?? user?.username?.[0] ?? '?';

  return (
    <nav
      aria-label="Navigation principale"
      style={{ display: 'flex', alignItems: 'center', width: '100%' }}
    >
      <div
        style={{
          fontSize: 18,
          fontWeight: 700,
          color: '#00874E',
          marginRight: 32,
          whiteSpace: 'nowrap',
        }}
      >
        IDP Portal
      </div>

      <Tabs
        activeKey={activeKey}
        items={tabItems}
        onChange={handleTabChange}
        style={{ flex: 1 }}
        tabBarStyle={{ marginBottom: 0, borderBottom: 'none' }}
      />

      {user && (
        <Dropdown menu={{ items: profileMenuItems }} trigger={['click']} placement="bottomRight">
          <Space
            style={{ cursor: 'pointer', marginLeft: 16 }}
            role="button"
            aria-label="Menu profil utilisateur"
            tabIndex={0}
          >
            <Avatar
              style={{ backgroundColor: '#00874E' }}
              icon={!avatarLetter || avatarLetter === '?' ? <UserOutlined /> : undefined}
            >
              {avatarLetter !== '?' ? avatarLetter.toUpperCase() : null}
            </Avatar>
          </Space>
        </Dropdown>
      )}
    </nav>
  );
}

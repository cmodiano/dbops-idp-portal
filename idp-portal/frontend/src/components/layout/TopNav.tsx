import './TopNav.css';
import { Dropdown, Avatar, Space, Typography, theme, Badge } from 'antd';
import {
  AppstoreOutlined,
  PlayCircleOutlined,
  DashboardOutlined,
  SettingOutlined,
  LogoutOutlined,
  UserOutlined,
  SunOutlined,
  MoonOutlined,
  AuditOutlined,
} from '@ant-design/icons';
import { useNavigate, useLocation } from 'react-router';
import { useAuth } from '../../contexts/AuthContext';
import { useTheme } from '../../contexts/ThemeContext';
import { useDashboard } from '../../contexts/DashboardContext';
import type { NavigationTabKey } from '../../types/common';
import type { MenuProps } from 'antd';

const { Text } = Typography;

const TAB_CONFIG: Record<NavigationTabKey, { label: string; icon: React.ReactNode }> = {
  catalog: { label: 'Catalogue', icon: <AppstoreOutlined /> },
  executions: { label: 'Exécutions', icon: <PlayCircleOutlined /> },
  dashboard: { label: 'Dashboard', icon: <DashboardOutlined /> },
  admin: { label: 'Admin', icon: <SettingOutlined /> },
  audit: { label: 'Audit', icon: <AuditOutlined /> },
};

const TAB_ROUTES: Record<NavigationTabKey, string> = {
  catalog: '/catalog',
  executions: '/executions',
  dashboard: '/dashboard',
  admin: '/admin',
  audit: '/audit',
};

export function TopNav() {
  const navigate = useNavigate();
  const location = useLocation();
  const { user, logout } = useAuth();
  const { effectiveMode, toggleTheme } = useTheme();
  const { token } = theme.useToken();
  const { unseenErrorCount } = useDashboard();

  const navigationTabs = user?.navigation_tabs ?? [];

  const activeKey = navigationTabs.find((key) =>
    location.pathname.startsWith(TAB_ROUTES[key]),
  );

  const handleNavClick = (key: NavigationTabKey) => {
    const route = TAB_ROUTES[key];
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
      label: <Text type="secondary" style={{ textTransform: 'capitalize' }}>{user?.profile?.replace('_', ' ') ?? ''}</Text>,
      disabled: true,
    },
    { type: 'divider' },
    {
      key: 'logout',
      label: 'Déconnexion',
      icon: <LogoutOutlined />,
      danger: true,
      onClick: () => logout(),
    },
  ];

  const avatarLetter = user?.display_name?.[0] ?? user?.username?.[0] ?? '?';
  const isDark = effectiveMode === 'dark';

  return (
    <nav
      aria-label="Navigation principale"
      style={{ display: 'flex', alignItems: 'center', width: '100%', gap: 8 }}
    >
      {/* Logo */}
      <div
        className="nav-logo"
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 10,
          marginRight: 24,
          cursor: 'pointer',
        }}
        onClick={() => navigate('/catalog')}
      >
        <img
          src="/logo-dbops.svg"
          alt="Logo Portail DBOPS"
          style={{ height: 36, width: 36 }}
        />
        <span
          style={{
            fontSize: 17,
            fontWeight: 600,
            color: token.colorPrimary,
            letterSpacing: '-0.02em',
          }}
        >
          DBOPS
        </span>
      </div>

      {/* Navigation Pills */}
      <div className="nav-pills" style={{ display: 'flex', gap: 4, flex: 1 }}>
        {navigationTabs.map((key) => {
          const isActive = key === activeKey;
          const config = TAB_CONFIG[key];
          const showBadge = key === 'dashboard' && unseenErrorCount > 0 && !isActive;
          const dashboardAriaLabel =
            key === 'dashboard' && unseenErrorCount > 0
              ? `Dashboard (${unseenErrorCount} erreur${unseenErrorCount > 1 ? 's' : ''} non vue${unseenErrorCount > 1 ? 's' : ''})`
              : undefined;
          const buttonContent = (
            <button
              key={key}
              onClick={() => handleNavClick(key)}
              className={`nav-pill ${isActive ? 'nav-pill-active' : ''}`}
              aria-label={dashboardAriaLabel}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 6,
                padding: '8px 16px',
                border: 'none',
                borderRadius: 8,
                cursor: 'pointer',
                fontSize: 14,
                fontWeight: 500,
                transition: 'all 0.2s ease',
                background: isActive
                  ? isDark ? 'rgba(0, 135, 78, 0.15)' : 'rgba(0, 135, 78, 0.1)'
                  : 'transparent',
                color: isActive
                  ? token.colorPrimary
                  : token.colorTextSecondary,
              }}
            >
              {config?.icon}
              <span>{config?.label ?? key}</span>
            </button>
          );
          // Show badge for dashboard when there are unseen errors (Story 5.2, AC2)
          return showBadge ? (
            <Badge
              key={key}
              dot
              offset={[-4, 4]}
              style={{ backgroundColor: token.colorError }}
            >
              {buttonContent}
            </Badge>
          ) : (
            <span key={key}>{buttonContent}</span>
          );
        })}
      </div>

      {/* Right section */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        {/* Theme Toggle - Modern pill */}
        <button
          onClick={toggleTheme}
          aria-label={isDark ? 'Activer le theme clair' : 'Activer le theme sombre'}
          role="switch"
          aria-checked={isDark}
          className="theme-toggle"
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            width: 40,
            height: 40,
            border: 'none',
            borderRadius: 10,
            cursor: 'pointer',
            transition: 'all 0.2s ease',
            background: token.colorFillTertiary,
            color: token.colorPrimary,
            fontSize: 18,
          }}
        >
          {isDark ? <SunOutlined /> : <MoonOutlined />}
        </button>

        {/* Profile */}
        {user && (
          <Dropdown menu={{ items: profileMenuItems }} trigger={['click']} placement="bottomRight">
            <Space
              className="nav-profile"
              style={{
                cursor: 'pointer',
                padding: '6px 12px 6px 8px',
                borderRadius: 10,
                transition: 'all 0.2s ease',
                background: isDark ? 'rgba(255, 255, 255, 0.05)' : 'rgba(0, 0, 0, 0.02)',
              }}
              role="button"
              aria-label="Menu profil utilisateur"
              tabIndex={0}
            >
              <Avatar
                size={32}
                style={{
                  backgroundColor: token.colorPrimary,
                  fontSize: 14,
                  fontWeight: 600,
                }}
                icon={!avatarLetter || avatarLetter === '?' ? <UserOutlined /> : undefined}
              >
                {avatarLetter !== '?' ? avatarLetter.toUpperCase() : null}
              </Avatar>
              <div style={{ display: 'flex', flexDirection: 'column', lineHeight: 1.2 }}>
                <Text style={{ fontSize: 13, fontWeight: 500 }}>
                  {user.display_name?.split(' ')[0] ?? user.username}
                </Text>
                <Text type="secondary" style={{ fontSize: 11, textTransform: 'capitalize' }}>
                  {user.profile?.replace('_', ' ')}
                </Text>
              </div>
            </Space>
          </Dropdown>
        )}
      </div>
    </nav>
  );
}

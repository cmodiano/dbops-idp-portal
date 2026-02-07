import './TopNav.css';
import { Dropdown, Avatar, Space, Typography, theme, Badge, Tooltip } from 'antd';
import {
  AppstoreOutlined,
  PlayCircleOutlined,
  CalendarOutlined,
  BarChartOutlined,
  SettingOutlined,
  LogoutOutlined,
  UserOutlined,
  SunOutlined,
  MoonOutlined,
  AuditOutlined,
  BellOutlined,
} from '@ant-design/icons';
import { useNavigate, useLocation } from 'react-router';
import { useAuth } from '../../contexts/AuthContext';
import { useTheme } from '../../contexts/ThemeContext';
import { useDashboard } from '../../contexts/DashboardContext';
import { usePendingApprovalsCount } from '../../hooks/usePendingApprovalsCount';
import type { NavigationTabKey } from '../../types/common';
import type { MenuProps } from 'antd';

const { Text } = Typography;

// Story 9.10: Dashboard renamed to Analytics (DBOPS only for advanced reporting)
// Story 13.6: Calendar menu for DBA/DBOPS to view scheduled executions
const TAB_CONFIG: Record<NavigationTabKey, { label: string; icon: React.ReactNode }> = {
  catalog: { label: 'Catalogue', icon: <AppstoreOutlined /> },
  executions: { label: 'Exécutions', icon: <PlayCircleOutlined /> },
  calendar: { label: 'Calendrier', icon: <CalendarOutlined /> },
  dashboard: { label: 'Analytics', icon: <BarChartOutlined /> },
  admin: { label: 'Admin', icon: <SettingOutlined /> },
  audit: { label: 'Audit', icon: <AuditOutlined /> },
};

// Story 9.10: Dashboard route renamed to /analytics
// Story 13.6: Calendar route for scheduled executions view
const TAB_ROUTES: Record<NavigationTabKey, string> = {
  catalog: '/catalog',
  executions: '/executions',
  calendar: '/calendar',
  dashboard: '/analytics',
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
  const { count: pendingApprovalsCount, error: approvalsError } = usePendingApprovalsCount();

  const navigationTabs = user?.navigation_tabs ?? [];

  // Story 8.8 AC9: Only DBA/DBOPS see bell icon
  const showApprovalsBell =
    user?.profile?.toLowerCase() === 'dba' ||
    user?.profile?.toLowerCase() === 'dbops';

  // Story 8.8 AC5: Navigate to executions page and scroll to pending-approvals section
  const handleBellClick = () => {
    navigate('/executions');
    setTimeout(() => {
      document.getElementById('pending-approvals')?.scrollIntoView({ behavior: 'smooth' });
    }, 100);
  };

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
        role="link"
        tabIndex={0}
        aria-label="Accueil — Catalogue"
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 10,
          marginRight: 24,
          cursor: 'pointer',
        }}
        onClick={() => navigate('/catalog')}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            navigate('/catalog');
          }
        }}
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
              ? `Analytics (${unseenErrorCount} erreur${unseenErrorCount > 1 ? 's' : ''} non vue${unseenErrorCount > 1 ? 's' : ''})`
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
        {/* Story 8.8 AC4: Approvals bell notification */}
        {showApprovalsBell && (
          <Tooltip title={approvalsError ? 'Erreur de chargement des approbations' : undefined}>
            <Badge
              count={pendingApprovalsCount}
              offset={[-5, 5]}
              style={{ backgroundColor: token.colorPrimary }}
              showZero={false}
            >
              <button
                onClick={handleBellClick}
                aria-label={
                  pendingApprovalsCount === 0
                    ? 'Aucune approbation en attente'
                    : `${pendingApprovalsCount} approbation${pendingApprovalsCount !== 1 ? 's' : ''} en attente`
                }
                role="button"
                tabIndex={0}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    handleBellClick();
                  }
                }}
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
                  color: pendingApprovalsCount > 0 ? token.colorPrimary : token.colorTextSecondary,
                  fontSize: 20,
                }}
              >
                <BellOutlined />
              </button>
            </Badge>
          </Tooltip>
        )}

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

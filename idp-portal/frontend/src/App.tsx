import { ConfigProvider, App as AntApp, Spin } from 'antd';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router';
import { lazy, Suspense, useEffect } from 'react';
import { lightTheme, darkTheme } from './theme/desjardins';
import { AppLayout } from './components/layout/AppLayout';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import { ThemeProvider, useTheme } from './contexts/ThemeContext';
import { DashboardProvider } from './contexts/DashboardContext';
import { FeatureFlagProvider } from './contexts/FeatureFlagContext';
import { ProtectedRoute } from './components/auth/ProtectedRoute';
import './styles/glass.css';
import './styles/recharts-tooltips.css';

const CatalogPage = lazy(() => import('./pages/CatalogPage'));
const ExecutionsPage = lazy(() => import('./pages/ExecutionsPage'));
const CalendarPage = lazy(() => import('./pages/CalendarPage'));
const DashboardPage = lazy(() => import('./pages/DashboardPage'));
const AdminPage = lazy(() => import('./pages/AdminPage'));
const AuditPage = lazy(() => import('./pages/AuditPage'));
const ApiKeysPage = lazy(() => import('./pages/ApiKeysPage'));
const NotFoundPage = lazy(() => import('./pages/NotFoundPage'));
const LoginPage = lazy(() => import('./pages/LoginPage'));
const AuthCallbackPage = lazy(() => import('./pages/AuthCallbackPage'));

function AdminGuard({ children }: { children: React.ReactNode }) {
  const { hasTab } = useAuth();
  if (!hasTab('admin')) {
    return <Navigate to="/catalog" replace />;
  }
  return <>{children}</>;
}

function AuditGuard({ children }: { children: React.ReactNode }) {
  const { hasTab, user } = useAuth();
  // Story 6.3, AC8: Access restricted to auditors
  if (!hasTab('audit') && !user?.is_auditor) {
    return <Navigate to="/catalog" replace />;
  }
  return <>{children}</>;
}

// Story 56.3: Analytics access based on navigation_tabs (hasTab) instead of profile name
function AnalyticsGuard({ children }: { children: React.ReactNode }) {
  const { hasTab } = useAuth();
  if (!hasTab('dashboard')) {
    return <Navigate to="/executions" replace />;
  }
  return <>{children}</>;
}

// Story 13.6 AC1: Calendar restricted to admin profiles (profiles with 'calendar' navigation tab)
function CalendarGuard({ children }: { children: React.ReactNode }) {
  const { hasTab } = useAuth();
  // Only admin profiles have 'calendar' in their navigation_tabs
  if (!hasTab('calendar')) {
    return <Navigate to="/catalog" replace />;
  }
  return <>{children}</>;
}

/**
 * Inner app component that uses theme context.
 * Applies theme to ConfigProvider and updates body background.
 */
function ThemedApp() {
  const { effectiveMode } = useTheme();
  const currentTheme = effectiveMode === 'dark' ? darkTheme : lightTheme;

  // Liquid glass: body gradient so frosted panels have depth; theme class for CSS
  useEffect(() => {
    const isDark = effectiveMode === 'dark';
    document.body.style.margin = '0';
    document.body.style.minHeight = '100vh';
    document.body.style.transition = 'background 0.4s ease';
    if (isDark) {
      document.body.style.background =
        'linear-gradient(165deg, #0f0f16 0%, #12121a 35%, #14141e 70%, #12121a 100%)';
    } else {
      document.body.style.background =
        'linear-gradient(165deg, #e8ecf2 0%, #e2e8f0 40%, #dde4ed 70%, #d8e0ea 100%)';
    }
    document.documentElement.style.colorScheme = effectiveMode;
    document.documentElement.classList.remove('light', 'dark');
    document.documentElement.classList.add(effectiveMode);

    return () => {
      document.body.style.background = '';
      document.body.style.minHeight = '';
      document.body.style.transition = '';
      document.body.style.margin = '';
      document.documentElement.style.colorScheme = '';
      document.documentElement.classList.remove('light', 'dark');
    };
  }, [effectiveMode]);

  return (
    <ConfigProvider theme={currentTheme}>
      <AntApp>
        <BrowserRouter>
          <AuthProvider>
            <FeatureFlagProvider>
            <DashboardProvider>
              <Suspense fallback={<div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '60vh' }}><Spin size="large" /></div>}>
                <Routes>
                <Route path="/login" element={<LoginPage />} />
                <Route path="/auth/callback" element={<AuthCallbackPage />} />
                <Route element={<ProtectedRoute><AppLayout /></ProtectedRoute>}>
                  <Route index element={<Navigate to="/catalog" replace />} />
                  <Route path="/catalog" element={<CatalogPage />} />
                  <Route path="/executions" element={<ExecutionsPage />} />
                  <Route path="/executions/:id" element={<ExecutionsPage />} />
                  {/* Story 13.6: Calendar for admin profiles to view scheduled executions */}
                  <Route path="/calendar" element={<CalendarGuard><CalendarPage /></CalendarGuard>} />
                  {/* Story 9.10: Dashboard renamed to Analytics — Story 56.3: access restricted to users with 'dashboard' in navigation_tabs (hasTab) */}
                  <Route path="/analytics" element={<AnalyticsGuard><DashboardPage /></AnalyticsGuard>} />
                  {/* Backward compatibility: redirect /dashboard to /analytics */}
                  <Route path="/dashboard" element={<Navigate to="/analytics" replace />} />
                  <Route path="/admin" element={<AdminGuard><AdminPage /></AdminGuard>} />
                  <Route path="/audit" element={<AuditGuard><AuditPage /></AuditGuard>} />
                  <Route path="/api-keys" element={<ApiKeysPage />} />
                </Route>
                <Route path="*" element={<NotFoundPage />} />
                </Routes>
              </Suspense>
            </DashboardProvider>
            </FeatureFlagProvider>
          </AuthProvider>
        </BrowserRouter>
      </AntApp>
    </ConfigProvider>
  );
}

export function App() {
  return (
    <ThemeProvider>
      <ThemedApp />
    </ThemeProvider>
  );
}

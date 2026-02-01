import { ConfigProvider, App as AntApp } from 'antd';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router';
import { lazy, Suspense, useEffect } from 'react';
import { lightTheme, darkTheme } from './theme/desjardins';
import { AppLayout } from './components/layout';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import { ThemeProvider, useTheme } from './contexts/ThemeContext';
import { DashboardProvider } from './contexts/DashboardContext';
import { ProtectedRoute } from './components/auth/ProtectedRoute';
import './styles/glass.css';

const CatalogPage = lazy(() => import('./pages/CatalogPage'));
const ExecutionsPage = lazy(() => import('./pages/ExecutionsPage'));
const DashboardPage = lazy(() => import('./pages/DashboardPage'));
const AdminPage = lazy(() => import('./pages/AdminPage'));
const AuditPage = lazy(() => import('./pages/AuditPage'));
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
        'linear-gradient(165deg, #0d0d12 0%, #12121a 35%, #0f0f16 70%, #0a0a0f 100%)';
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
            <DashboardProvider>
              <Suspense fallback={null}>
                <Routes>
                <Route path="/login" element={<LoginPage />} />
                <Route path="/auth/callback" element={<AuthCallbackPage />} />
                <Route element={<ProtectedRoute><AppLayout /></ProtectedRoute>}>
                  <Route index element={<Navigate to="/catalog" replace />} />
                  <Route path="/catalog" element={<CatalogPage />} />
                  <Route path="/executions" element={<ExecutionsPage />} />
                  <Route path="/dashboard" element={<DashboardPage />} />
                  <Route path="/admin" element={<AdminGuard><AdminPage /></AdminGuard>} />
                  <Route path="/audit" element={<AuditGuard><AuditPage /></AuditGuard>} />
                </Route>
                <Route path="*" element={<NotFoundPage />} />
                </Routes>
              </Suspense>
            </DashboardProvider>
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

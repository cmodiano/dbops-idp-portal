import { ConfigProvider, App as AntApp } from 'antd';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router';
import { lazy, Suspense, useEffect } from 'react';
import { lightTheme, darkTheme } from './theme/desjardins';
import { AppLayout } from './components/layout';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import { ThemeProvider, useTheme } from './contexts/ThemeContext';
import { ProtectedRoute } from './components/auth/ProtectedRoute';
import './styles/glass.css';

const CatalogPage = lazy(() => import('./pages/CatalogPage'));
const ExecutionsPage = lazy(() => import('./pages/ExecutionsPage'));
const DashboardPage = lazy(() => import('./pages/DashboardPage'));
const AdminPage = lazy(() => import('./pages/AdminPage'));
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

/**
 * Inner app component that uses theme context.
 * Applies theme to ConfigProvider and updates body background.
 */
function ThemedApp() {
  const { effectiveMode } = useTheme();
  const currentTheme = effectiveMode === 'dark' ? darkTheme : lightTheme;

  // Update body background color and theme class for smooth transitions (AC #3)
  useEffect(() => {
    const bgColor = effectiveMode === 'dark' ? '#0f0f14' : '#f4f6f8';
    document.body.style.backgroundColor = bgColor;
    document.body.style.transition = 'background-color 0.3s ease';
    document.body.style.margin = '0';

    // Set color-scheme for native elements (scrollbars, inputs)
    document.documentElement.style.colorScheme = effectiveMode;

    // Add theme class for CSS targeting
    document.documentElement.classList.remove('light', 'dark');
    document.documentElement.classList.add(effectiveMode);

    return () => {
      document.body.style.backgroundColor = '';
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
                </Route>
                <Route path="*" element={<NotFoundPage />} />
              </Routes>
            </Suspense>
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

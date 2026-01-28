import { ConfigProvider } from 'antd';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router';
import { lazy, Suspense } from 'react';
import { desjardinsTheme } from './theme/desjardins';
import { AppLayout } from './components/layout';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import { ProtectedRoute } from './components/auth/ProtectedRoute';

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

export function App() {
  return (
    <ConfigProvider theme={desjardinsTheme}>
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
    </ConfigProvider>
  );
}

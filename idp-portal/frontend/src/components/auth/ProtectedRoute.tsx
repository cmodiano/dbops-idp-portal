import { Navigate } from 'react-router';
import { Spin } from 'antd';
import { useAuth } from '../../contexts/AuthContext';
import type { ReactNode } from 'react';

export function ProtectedRoute({ children }: { children: ReactNode }) {
  const { isAuthenticated, isLoading } = useAuth();

  if (isLoading) {
    // Story 66.2 F6 (LOW): show spinner instead of blank screen during auth check
    return <Spin size="large" style={{ display: 'block', margin: '100px auto' }} />;
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  return <>{children}</>;
}

/**
 * ExecutionsTabs - Tab navigation for execution scope (Story 8.9, AC1, AC6).
 *
 * Features:
 * - Tabs: "Toutes les exécutions" (DBA/DBOPS only), "Mes exécutions"
 * - RBAC: non-DBA/DBOPS users only see "Mes exécutions" tab
 * - Active tab with indicator
 * - Keyboard accessible (native Ant Design Tabs)
 */

import { Tabs } from 'antd';
import { useTheme } from '../../contexts/ThemeContext';
import type { ExecutionScope } from '../../types/api';

export interface ExecutionsTabsProps {
  /** Currently active scope. */
  activeScope: ExecutionScope;
  /** Callback when scope changes. */
  onScopeChange: (scope: ExecutionScope) => void;
  /** RBAC: true if user can view all executions (DBA/DBOPS). */
  canViewAll: boolean;
}

/**
 * Tabs component for filtering executions by scope.
 * - "Toutes les exécutions": Shows all executions (DBA/DBOPS only)
 * - "Mes exécutions": Shows only the current user's executions
 */
export function ExecutionsTabs({
  activeScope,
  onScopeChange,
  canViewAll,
}: ExecutionsTabsProps) {
  const { effectiveMode } = useTheme();
  const isDark = effectiveMode === 'dark';

  // If user cannot view all executions, only show "Mes exécutions" tab
  const items = canViewAll
    ? [
        { key: 'all', label: 'Toutes les exécutions' },
        { key: 'mine', label: 'Mes exécutions' },
      ]
    : [{ key: 'mine', label: 'Mes exécutions' }];

  return (
    <Tabs
      activeKey={activeScope}
      onChange={(key) => onScopeChange(key as ExecutionScope)}
      items={items}
      style={{ marginBottom: 16 }}
      tabBarStyle={{
        borderBottom: isDark ? '1px solid rgba(255, 255, 255, 0.12)' : '1px solid #e8e8e8',
      }}
      indicator={{
        size: (origin) => origin - 16,
        align: 'center',
      }}
    />
  );
}

export default ExecutionsTabs;

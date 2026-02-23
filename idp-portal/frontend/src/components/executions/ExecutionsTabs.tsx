/**
 * ExecutionsTabs - Tab navigation for execution scope (Story 8.9, AC1, AC6).
 *
 * Features:
 * - Tabs: "Toutes les exécutions" (tous les utilisateurs), "Mes exécutions"
 * - Story 36.1 AC1: les deux onglets sont visibles pour tous les utilisateurs authentifiés.
 *   Le backend applique le filtrage RBAC par actions autorisées.
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
  /**
   * @deprecated Story 36.1: tous les utilisateurs voient les deux onglets.
   * Le backend applique le filtrage RBAC. Cette prop est conservée pour
   * compatibilité mais n'est plus utilisée dans le rendu du composant.
   */
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

  // Story 36.1 AC1: les deux onglets sont toujours visibles.
  // Le backend filtre les exécutions selon les droits RBAC de l'utilisateur.
  // canViewAll est conservé dans l'interface pour rétrocompatibilité.
  const items = [
    { key: 'all', label: 'Toutes les exécutions' },
    { key: 'mine', label: 'Mes exécutions' },
  ];

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

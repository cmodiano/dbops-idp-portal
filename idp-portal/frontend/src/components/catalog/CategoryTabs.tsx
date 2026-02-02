/**
 * CategoryTabs - Tab navigation for catalog categories (Story 8.7, AC1, AC2).
 *
 * Features:
 * - Tabs: "Tout", "Provisioning", "Patching", "Administration", "Monitoring", "Backup", "Mes actions"
 * - Active tab with Desjardins green #00874E + underline
 * - ARIA: role="tablist", aria-selected, aria-controls
 * - Keyboard accessible (AC6)
 */

import { Tabs } from 'antd';
import { HeartOutlined } from '@ant-design/icons';
import { useTheme } from '../../contexts/ThemeContext';
import { STYLE_TOKENS } from '../../theme/styleTokens';

/** Category definitions for catalog navigation (Story 8.7: labels in French). */
export const CATEGORIES = [
  { key: 'tout', label: 'Tout' },
  { key: 'provisioning', label: 'Approvisionnement' },
  { key: 'patching', label: 'Correctifs' },
  { key: 'administration', label: 'Administration' },
  { key: 'monitoring', label: 'Surveillance' },
  { key: 'backup', label: 'Sauvegarde' },
  { key: 'mes-actions', label: 'Mes actions' },
] as const;

export type CategoryKey = (typeof CATEGORIES)[number]['key'];

export interface CategoryTabsProps {
  /** Currently active category key. */
  activeCategory: CategoryKey;
  /** Callback when category changes. */
  onCategoryChange: (category: CategoryKey) => void;
  /** Optional favorites count for "Mes actions" badge. */
  favoritesCount?: number;
}

/**
 * Category tabs component for filtering catalog by action categories.
 * Maps to backend tag filtering (e.g., category "patching" filters by tag "patching").
 */
export function CategoryTabs({
  activeCategory,
  onCategoryChange,
  favoritesCount = 0,
}: CategoryTabsProps) {
  const { effectiveMode } = useTheme();
  const isDark = effectiveMode === 'dark';

  const items = CATEGORIES.map((cat) => ({
    key: cat.key,
    label: (
      <span>
        {cat.key === 'mes-actions' && <HeartOutlined style={{ marginRight: 4 }} />}
        {cat.key === 'mes-actions' && favoritesCount > 0
          ? `${cat.label} (${favoritesCount})`
          : cat.label}
      </span>
    ),
  }));

  return (
    <Tabs
      activeKey={activeCategory}
      onChange={(key) => onCategoryChange(key as CategoryKey)}
      items={items}
      style={{ marginBottom: 16 }}
      tabBarStyle={{
        borderBottom: isDark ? '1px solid rgba(255, 255, 255, 0.12)' : '1px solid #e8e8e8',
      }}
      // Active tab indicator uses Desjardins green
      indicator={{
        size: (origin) => origin - 16,
        align: 'center',
      }}
    />
  );
}

export default CategoryTabs;

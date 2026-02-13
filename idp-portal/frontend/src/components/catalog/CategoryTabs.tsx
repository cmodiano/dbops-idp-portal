/**
 * CategoryTabs - Tab navigation for catalog categories (Story 8.7, AC1, AC2; Story 2.30, AC6).
 *
 * Features:
 * - Dynamic tabs from REF_CATEGORIES (Story 2.30: replaces hard-coded CATEGORIES)
 * - Fixed tabs: "Tout" (first) and "Mes actions" (last)
 * - Active tab with Desjardins green #00874E + underline
 * - ARIA: role="tablist", aria-selected, aria-controls
 * - Keyboard accessible (AC6)
 */

import { Tabs, Skeleton } from 'antd';
import { HeartOutlined } from '@ant-design/icons';
import { useTheme } from '../../contexts/ThemeContext';
import { useCategories } from '../../hooks/useCategories';

export type CategoryKey = string;

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
 * Story 2.30, AC6: Dynamic categories loaded from REF_CATEGORIES API.
 */
export function CategoryTabs({
  activeCategory,
  onCategoryChange,
  favoritesCount = 0,
}: CategoryTabsProps) {
  const { effectiveMode } = useTheme();
  const isDark = effectiveMode === 'dark';
  const { categoryOptions, loading: categoriesLoading } = useCategories();

  if (categoriesLoading) {
    return <Skeleton.Input active style={{ width: 400, marginBottom: 16 }} />;
  }

  // Build tabs: "Tout" + dynamic categories + "Mes actions"
  const dynamicItems = categoryOptions.map((cat) => ({
    key: cat.value,
    label: <span>{cat.label}</span>,
  }));

  const items = [
    { key: 'tout', label: <span>Tout</span> },
    ...dynamicItems,
    {
      key: 'mes-actions',
      label: (
        <span>
          <HeartOutlined style={{ marginRight: 4 }} />
          {favoritesCount > 0 ? `Mes actions (${favoritesCount})` : 'Mes actions'}
        </span>
      ),
    },
  ];

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

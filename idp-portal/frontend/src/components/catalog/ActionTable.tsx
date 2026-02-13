/**
 * ActionTable - Table view component for catalog actions (Story 8.10).
 *
 * Features:
 * - AC1: Table Ant Design with columns: Action, Description, Impact, Tags, Moteur, Exécutions, Favori, Actions
 * - AC2: Action column with icon (workflow or engine) and bold name
 * - AC3: Description truncated to 2 lines with ellipsis and tooltip
 * - AC4: Impact column with ImpactIndicator (triple coding)
 * - AC5: Tags column with max 3 visible + "+N" tooltip
 * - AC6: Exécutions column formatted "N exécution(s)"
 * - AC7: Favori column with interactive heart toggle
 * - AC8: Actions column with "Voir détails" button
 * - AC9: Column sorting (name, engine, impact, executions)
 * - AC10: Row hover effect with pointer cursor
 * - AC11: Skeleton loading via Table loading prop
 * - AC12: Responsive design - hide Description and Tags on mobile
 */

import React, { useMemo, useCallback } from 'react';
import {
  Table,
  Typography,
  Space,
  Tag,
  Tooltip,
  Button,
  theme,
} from 'antd';
import type { TableProps } from 'antd';

import {
  HeartOutlined,
  HeartFilled,
  EyeOutlined,
} from '@ant-design/icons';
import type { CatalogAction } from '../../services/catalog_service';
import type { ImpactLevel } from '../../types/api';
import { ImpactIndicator } from '../shared/ImpactIndicator';
import { getTagStyle } from '../../utils/tagStyles';
import { getItemTypeIcon } from '../../utils/iconHelpers';
import { useTheme } from '../../contexts/ThemeContext';

const { Text, Paragraph } = Typography;

// Constants (L1 fix)
const MAX_DESCRIPTION_WIDTH = 280;
const MAX_DESCRIPTION_TOOLTIP_LENGTH = 200;

export interface ActionTableProps {
  /** List of actions to display */
  actions: CatalogAction[];
  /** Set of favorite action IDs */
  favorites: Set<number>;
  /** Loading state for skeleton display */
  loading: boolean;
  /** Callback when action row is clicked */
  onActionClick: (action: CatalogAction) => void;
  /** Callback when favorite is toggled */
  onToggleFavorite: (actionId: number, e: React.MouseEvent) => void;
  /** Whether to show favorite button (requires auth) */
  showFavoriteButton?: boolean;
}

/** Map impact level to numeric value for sorting (AC9) */
const getImpactSortValue = (level: ImpactLevel | null | undefined): number => {
  const mapping: Record<ImpactLevel, number> = {
    low: 1,
    medium: 2,
    high: 3,
    critical: 4,
  };
  return level ? mapping[level] : 0;
};

/** Get appropriate icon for action based on item_type and engine (AC2) - Story 18.2: use shared iconHelpers */
const getActionIcon = (action: CatalogAction): React.ReactNode => {
  const { icon } = getItemTypeIcon(action.item_type, action.engine, { fontSize: 18 });
  return icon;
};

export function ActionTable({
  actions,
  favorites,
  loading,
  onActionClick,
  onToggleFavorite,
  showFavoriteButton = true,
}: ActionTableProps) {
  const { token } = theme.useToken();
  const { effectiveMode } = useTheme();
  const isDark = effectiveMode === 'dark';

  /** Render tags with max 3 visible + "+N" (AC5) - H1 fix: wrapped in useCallback */
  const renderTags = useCallback((tags: string[] | undefined): React.ReactNode => {
    if (!tags || tags.length === 0) {
      return <Text type="secondary">Aucun tag</Text>;
    }

    const visibleTags = tags.slice(0, 3);
    const hiddenCount = tags.length - 3;

    return (
      <Space size={4} wrap>
        {visibleTags.map((tag) => {
          const tagStyle = getTagStyle(tag, isDark);
          return (
            <Tag
              key={tag}
              style={{
                margin: 0,
                borderRadius: 16,
                padding: '2px 10px',
                fontSize: 12,
                ...tagStyle,
              }}
            >
              {tag}
            </Tag>
          );
        })}
        {hiddenCount > 0 && (
          <Tooltip title={tags.slice(3).join(', ')}>
            <Tag
              style={{
                margin: 0,
                borderRadius: 16,
                padding: '2px 10px',
                fontSize: 12,
                background: 'rgba(150,150,150,0.2)',
                color: 'inherit',
                border: 'none',
              }}
            >
              +{hiddenCount}
            </Tag>
          </Tooltip>
        )}
      </Space>
    );
  }, [isDark]);

  const columns: TableProps<CatalogAction>['columns'] = useMemo(
    () => [
      // AC2: Action column with icon and name
      {
        title: 'Action',
        dataIndex: 'name',
        key: 'name',
        sorter: (a, b) => (a.name || '').localeCompare(b.name || ''),
        defaultSortOrder: 'ascend',
        render: (_: string, record: CatalogAction) => (
          <Space>
            {getActionIcon(record)}
            <Text strong>{record.name || 'Sans nom'}</Text>
          </Space>
        ),
        width: 250,
      },
      // AC3: Description column with truncation and tooltip (M3 fix: limit tooltip length)
      {
        title: 'Description',
        dataIndex: 'description',
        key: 'description',
        render: (text: string | null) => {
          if (!text) {
            return <Text type="secondary">Aucune description</Text>;
          }
          // M3 fix: Limit tooltip to avoid giant tooltips
          const tooltipText = text.length > MAX_DESCRIPTION_TOOLTIP_LENGTH
            ? `${text.substring(0, MAX_DESCRIPTION_TOOLTIP_LENGTH)}...`
            : text;
          return (
            <Tooltip title={tooltipText}>
              <Paragraph
                ellipsis={{ rows: 2 }}
                style={{ margin: 0, maxWidth: MAX_DESCRIPTION_WIDTH }}
              >
                {text}
              </Paragraph>
            </Tooltip>
          );
        },
        width: 300,
        responsive: ['md'],
      },
      // AC4: Impact column with ImpactIndicator
      {
        title: 'Impact',
        dataIndex: 'impact_level',
        key: 'impact_level',
        sorter: (a, b) =>
          getImpactSortValue(a.impact_level) - getImpactSortValue(b.impact_level),
        render: (level: ImpactLevel | null) => {
          if (!level) {
            return <Text type="secondary">N/A</Text>;
          }
          return <ImpactIndicator level={level} size="small" />;
        },
        width: 120,
        align: 'center',
      },
      // AC5: Tags column
      {
        title: 'Tags',
        dataIndex: 'tags',
        key: 'tags',
        render: renderTags,
        width: 200,
        responsive: ['md'],
      },
      // AC2, AC9: Moteur column with sort
      {
        title: 'Moteur',
        dataIndex: 'engine',
        key: 'engine',
        sorter: (a, b) => (a.engine || '').localeCompare(b.engine || ''),
        render: (engine: string | null) => engine || 'N/A',
        width: 120,
      },
      // AC6, AC9: Exécutions column with format and sort (M1 fix: proper French pluralization)
      {
        title: 'Exécutions',
        dataIndex: 'execution_count',
        key: 'execution_count',
        sorter: (a, b) => (a.execution_count ?? 0) - (b.execution_count ?? 0),
        render: (count: number | null) => {
          const value = count ?? 0;
          // M1 fix: French idiom uses plural for 0 and > 1, singular only for 1
          return `${value} exécution${value !== 1 ? 's' : ''}`;
        },
        width: 120,
        align: 'right',
      },
      // AC7: Favori column with toggle
      {
        title: 'Favori',
        key: 'favorite',
        render: (_: unknown, record: CatalogAction) => {
          if (!showFavoriteButton) return null;
          const isFavorite = favorites.has(record.id);
          return (
            <Tooltip title={isFavorite ? 'Retirer des favoris' : 'Ajouter aux favoris'}>
              <Button
                type="text"
                icon={isFavorite ? <HeartFilled /> : <HeartOutlined />}
                onClick={(e) => {
                  e.stopPropagation();
                  onToggleFavorite(record.id, e);
                }}
                style={{
                  color: isFavorite ? token.colorError : token.colorTextSecondary,
                }}
                aria-label={isFavorite ? 'Retirer des favoris' : 'Ajouter aux favoris'}
              />
            </Tooltip>
          );
        },
        width: 80,
        align: 'center',
      },
      // AC8: Actions column with details button
      {
        title: 'Actions',
        key: 'actions',
        render: (_: unknown, record: CatalogAction) => (
          <Button
            type="link"
            size="small"
            icon={<EyeOutlined />}
            onClick={(e) => {
              e.stopPropagation();
              onActionClick(record);
            }}
          >
            <span className="action-table-details-label">Voir détails</span>
          </Button>
        ),
        width: 140,
        align: 'center',
      },
    ],
    [favorites, showFavoriteButton, token, onActionClick, onToggleFavorite, renderTags]
  );

  // H2 fix: Extract styles to avoid inline <style> tag (CSP and performance issue)
  const tableStyles = useMemo(() => ({
    row: {
      cursor: 'pointer' as const,
      transition: 'background-color 0.2s ease',
    },
  }), []);

  return (
    <div className="action-table-container">
      <style>
        {`
          /* H2 partial fix: Keep minimal CSS for pseudo-classes that can't be inlined */
          .catalog-table-row:hover td {
            background-color: ${token.colorBgTextHover} !important;
          }
          @media (max-width: 767px) {
            .action-table-details-label {
              display: none;
            }
          }
        `}
      </style>
      <Table<CatalogAction>
        columns={columns}
        dataSource={actions}
        loading={loading}
        rowKey={(record) => record.id ?? `temp-${record.name}-${Math.random()}`} // H5 fix: fallback for missing ID
        onRow={(record) => ({
          onClick: () => onActionClick(record),
          className: 'catalog-table-row',
          style: tableStyles.row,
        })}
        pagination={{
          pageSize: 20,
          showSizeChanger: true,
          pageSizeOptions: ['10', '20', '50'],
          showTotal: (total) => `${total} action${total !== 1 ? 's' : ''}`, // M2 fix: consistent pluralization
        }}
        scroll={{ x: 'max-content' }}
        locale={{
          emptyText: 'Aucune action',
        }}
        data-testid="catalog-table" // L2 fix: add test ID
      />
    </div>
  );
}

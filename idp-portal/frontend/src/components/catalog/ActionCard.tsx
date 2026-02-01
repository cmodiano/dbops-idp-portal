/**
 * ActionCard - Reusable card component for catalog actions (Story 2.5, AC #1, #2; Story 5.7 AC3).
 *
 * Used in:
 * - Admin preview (Epic 2) with variant='preview'
 * - Catalog listing (Epic 3) with variant='default'
 *
 * Features:
 * - Engine icon (Oracle, SQL Server, DB2) for actions
 * - Workflow icon (ApartmentOutlined) for workflows (Story 5.7, AC3)
 * - Title (1 line, truncated)
 * - Description (2 lines, truncated)
 * - ImpactIndicator (triple coding)
 * - Tags (max 3 visible + "+N more")
 * - Hover effect (default variant only)
 * - Keyboard accessible (focusable, Enter to activate)
 */

import { Card, Tag, Typography, Space, Tooltip, Button } from 'antd';
import {
  DatabaseOutlined,
  CloudServerOutlined,
  HddOutlined,
  ApartmentOutlined,
  HeartOutlined,
  HeartFilled,
} from '@ant-design/icons';
import type { ActionPreviewData, ActionEngine, ItemType } from '../../types/api';
import { useTheme } from '../../contexts/ThemeContext';
import { ImpactIndicator } from '../shared/ImpactIndicator';
import { IMPACT_LABELS } from '../shared/impactLabels';
import { STYLE_TOKENS } from '../../theme/styleTokens';
import { getTagStyle } from '../../utils/tagStyles';

const { Text, Paragraph } = Typography;

export interface ActionCardProps {
  action: ActionPreviewData;
  onClick?: () => void;
  variant?: 'default' | 'preview';
  /** When set, shows favorite heart inside the card (catalog only). */
  isFavorite?: boolean;
  /** Called when favorite is toggled; caller should stopPropagation. */
  onToggleFavorite?: (e: React.MouseEvent) => void;
  /** Hide favorite button when not authenticated. */
  showFavoriteButton?: boolean;
}

const ENGINE_ICONS: Record<ActionEngine, React.ReactNode> = {
  Oracle: (
    <DatabaseOutlined
      style={{ fontSize: STYLE_TOKENS.engineIconSize, color: STYLE_TOKENS.engineIconColor.Oracle }}
    />
  ),
  'SQL Server': (
    <CloudServerOutlined
      style={{ fontSize: STYLE_TOKENS.engineIconSize, color: STYLE_TOKENS.engineIconColor['SQL Server'] }}
    />
  ),
  DB2: (
    <HddOutlined
      style={{ fontSize: STYLE_TOKENS.engineIconSize, color: STYLE_TOKENS.engineIconColor.DB2 }}
    />
  ),
};

/** Workflow icon - distinct from action icons (Story 5.7, AC3). */
const WORKFLOW_ICON = (
  <Tooltip title="Workflow (chaîne d'actions)">
    <ApartmentOutlined
      style={{ fontSize: STYLE_TOKENS.engineIconSize, color: '#722ed1' }}
    />
  </Tooltip>
);

const MAX_VISIBLE_TAGS = 3;

export function ActionCard({
  action,
  onClick,
  variant = 'default',
  isFavorite,
  onToggleFavorite,
  showFavoriteButton,
}: ActionCardProps) {
  const { effectiveMode } = useTheme();
  const isDark = effectiveMode === 'dark';
  const isPreview = variant === 'preview';
  const isClickable = !!onClick && !isPreview;
  const isWorkflow = action.item_type === 'workflow';

  // Story 5.7, AC3: Use workflow icon for workflows, engine icon for actions
  const icon = isWorkflow
    ? WORKFLOW_ICON
    : (action.engine ? ENGINE_ICONS[action.engine] : null);

  const visibleTags = action.tags?.slice(0, MAX_VISIBLE_TAGS) || [];
  const hiddenTagsCount = (action.tags?.length || 0) - MAX_VISIBLE_TAGS;
  const impactLabel = action.impact_level ? IMPACT_LABELS[action.impact_level] : null;
  const itemTypeLabel = isWorkflow ? 'Workflow' : 'Action';
  const ariaLabel = impactLabel
    ? `${itemTypeLabel}: ${action.name || 'Sans nom'}, impact ${impactLabel}`
    : `${itemTypeLabel}: ${action.name || 'Sans nom'}`;

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (isClickable && (e.key === 'Enter' || e.key === ' ')) {
      e.preventDefault();
      onClick?.();
    }
  };

  return (
    <Card
      role="article"
      aria-label={ariaLabel}
      tabIndex={isClickable ? 0 : undefined}
      onClick={isClickable ? onClick : undefined}
      onKeyDown={isClickable ? handleKeyDown : undefined}
      hoverable={isClickable}
      className={isPreview ? 'card-preview' : undefined}
      style={{
        width: '100%',
        maxWidth: STYLE_TOKENS.cardMaxWidth,
        cursor: isClickable ? 'pointer' : 'default',
        overflow: 'hidden',
      }}
      styles={{
        body: { padding: STYLE_TOKENS.cardBodyPadding },
      }}
    >
      <Space orientation="vertical" size="small" style={{ width: '100%' }}>
        {/* Header: Icon (workflow or engine) + Impact indicator — no overlap, badge stays inside card */}
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'flex-start',
            gap: 8,
            minWidth: 0,
            overflow: 'hidden',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, minWidth: 0, flex: 1 }}>
            {icon}
            <Text strong style={{ fontSize: 16 }} ellipsis={{ tooltip: action.name }}>
              {action.name || 'Sans nom'}
            </Text>
          </div>
          {action.impact_level && (
            <span style={{ flexShrink: 0 }}>
              <ImpactIndicator level={action.impact_level} size="small" />
            </span>
          )}
        </div>

        {/* Description (2 lines max) */}
        <Paragraph
          type="secondary"
          ellipsis={{ rows: 2, tooltip: action.description }}
          style={{ marginBottom: 8 }}
        >
          {action.description || 'Aucune description'}
        </Paragraph>

        {/* Tags — pastel, pill-shaped, user-friendly */}
        {visibleTags.length > 0 && (
          <Space size={6} wrap style={{ width: '100%' }}>
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
            {hiddenTagsCount > 0 && (
              <Tooltip title={action.tags?.slice(MAX_VISIBLE_TAGS).join(', ')}>
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
                  +{hiddenTagsCount}
                </Tag>
              </Tooltip>
            )}
          </Space>
        )}

        {/* Bottom row: execution count + optional favorite heart inside card */}
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            marginTop: 4,
          }}
        >
          {typeof action.execution_count === 'number' && action.execution_count >= 0 ? (
            <Text type="secondary" style={{ fontSize: 12 }}>
              {action.execution_count} exécution{action.execution_count !== 1 ? 's' : ''}
            </Text>
          ) : (
            <span />
          )}
          {showFavoriteButton && onToggleFavorite && (
            <Tooltip title={isFavorite ? 'Retirer des favoris' : 'Ajouter aux favoris'}>
              <Button
                type="text"
                size="small"
                icon={
                  isFavorite ? (
                    <HeartFilled style={{ color: '#f5222d', fontSize: 14 }} />
                  ) : (
                    <HeartOutlined style={{ fontSize: 14 }} />
                  )
                }
                onClick={(e) => {
                  e.stopPropagation();
                  onToggleFavorite(e);
                }}
                disabled={false}
                style={{
                  padding: 0,
                  width: 24,
                  height: 24,
                  minWidth: 24,
                  lineHeight: 1,
                  margin: -4,
                }}
                aria-label={isFavorite ? 'Retirer des favoris' : 'Ajouter aux favoris'}
              />
            </Tooltip>
          )}
        </div>
      </Space>
    </Card>
  );
}

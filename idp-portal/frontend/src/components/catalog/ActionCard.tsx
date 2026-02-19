/**
 * ActionCard - Reusable card component for catalog actions (Story 2.5, AC #1, #2; Story 5.7 AC3; Story 7.1).
 *
 * Used in:
 * - Admin preview (Epic 2) with variant='preview'
 * - Catalog listing (Epic 3) with variant='default'
 * - Business catalog (Story 7.1) with variant='business' - simplified descriptions
 *
 * Features:
 * - Engine icon (Oracle, SQL Server, DB2) for actions
 * - Workflow icon (ApartmentOutlined) for workflows (Story 5.7, AC3)
 * - Title (2 lines, truncated)
 * - Description (2 lines, truncated) - sanitized in business variant
 * - ImpactIndicator (triple coding)
 * - Tags (max 3 visible + "+N more")
 * - Hover effect (default variant only)
 * - Keyboard accessible (focusable, Enter to activate)
 */

import { Card, Tag, Typography, Space, Tooltip, Button } from 'antd';
import {
  HeartOutlined,
  HeartFilled,
} from '@ant-design/icons';
import type { ActionPreviewData, ActionEngine } from '../../types/api';
import { useTheme } from '../../contexts/ThemeContext';
import { ImpactIndicator } from '../shared/ImpactIndicator';
import { IMPACT_LABELS } from '../shared/impactLabels';
import { STYLE_TOKENS } from '../../theme/styleTokens';
import { getTagStyle } from '../../utils/tagStyles';
import { sanitizeDescription } from '../../utils/businessLanguage';
import { ENGINE_SVG_SOURCES } from '../../utils/executionRenderers';
import { getEngineIconUrl } from '../../utils/engineIconCache';
import { getItemTypeIcon } from '../../utils/iconHelpers';

const { Text, Paragraph } = Typography;

export interface ActionCardProps {
  action: ActionPreviewData;
  onClick?: () => void;
  /** 'default' = standard, 'preview' = admin preview, 'business' = simplified for business users (Story 7.1). */
  variant?: 'default' | 'preview' | 'business';
  /** When set, shows favorite heart inside the card (catalog only). */
  isFavorite?: boolean;
  /** Called when favorite is toggled; caller should stopPropagation. */
  onToggleFavorite?: (e: React.MouseEvent) => void;
  /** Hide favorite button when not authenticated. */
  showFavoriteButton?: boolean;
}

/** Get engine icon with SVG override for cards (real vendor logos).
 * Story 31.3: Fallback cascade — 1) icon_url from API cache, 2) ENGINE_SVG_SOURCES hardcoded, 3) iconHelpers. */
function getEngineIcon(engine: ActionEngine): React.ReactNode {
  const apiIconUrl = getEngineIconUrl(engine);
  const svgSrc = apiIconUrl || ENGINE_SVG_SOURCES[engine];
  if (svgSrc) {
    return (
      <img
        src={svgSrc}
        alt=""
        width={STYLE_TOKENS.engineIconSize}
        height={STYLE_TOKENS.engineIconSize}
        style={{ flexShrink: 0 }}
        aria-hidden
      />
    );
  }
  const { icon } = getItemTypeIcon('action', engine, { fontSize: STYLE_TOKENS.engineIconSize });
  return icon;
}

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
  const isBusiness = variant === 'business';
  const isClickable = !!onClick && !isPreview;
  const isWorkflow = action.item_type === 'workflow';

  // Story 7.1 AC2: Sanitize description for business users
  const displayDescription = isBusiness
    ? sanitizeDescription(action.description)
    : action.description;

  // Story 5.7, AC3; Story 18.2: Use shared iconHelpers for workflow, engine-specific SVG for actions
  const icon = isWorkflow
    ? getItemTypeIcon('workflow', null, { withTooltip: true, fontSize: STYLE_TOKENS.engineIconSize }).icon
    : (action.engine ? getEngineIcon(action.engine) : null);

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
        {/* Ligne 1: Icône technologie/workflow + impact */}
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            gap: 8,
            minWidth: 0,
          }}
        >
          <span style={{ flexShrink: 0 }}>{icon}</span>
          {action.impact_level && (
            <span style={{ flexShrink: 0 }}>
              <ImpactIndicator level={action.impact_level} size="small" />
            </span>
          )}
        </div>

        {/* Ligne 2: Titre */}
        <Paragraph
          strong
          style={{ margin: 0, fontSize: 16, lineHeight: 1.4 }}
          ellipsis={{ rows: 2, tooltip: action.name }}
        >
          {action.name || 'Sans nom'}
        </Paragraph>

        {/* Ligne 3: Description - sanitized for business variant (Story 7.1) */}
        <Paragraph
          type="secondary"
          ellipsis={{ rows: 2, tooltip: displayDescription }}
          style={{ marginBottom: 0 }}
        >
          {displayDescription || 'Aucune description'}
        </Paragraph>

        {/* Tags — pastel, pill-shaped */}
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

        {/* Bouton favori + compteur d'exécutions */}
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
                  width: 44,
                  height: 44,
                  minWidth: 44,
                  lineHeight: 1,
                  margin: -10,
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

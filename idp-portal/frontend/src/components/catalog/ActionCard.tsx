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

import { memo } from 'react';
import type { ReactNode, MouseEvent, KeyboardEvent } from 'react';
import { Card, Tag, Typography, Space, Tooltip, Button } from 'antd';
import {
  HeartOutlined,
  HeartFilled,
} from '@ant-design/icons';
import type { ActionPreviewData, ActionEngine, IncludedAction } from '../../types/api';
import { useTheme } from '../../contexts/ThemeContext';
import { useAuth } from '../../contexts/AuthContext';
import { ImpactIndicator } from '../shared/ImpactIndicator';
import { IMPACT_LABELS } from '../shared/impactLabels';
import { STYLE_TOKENS } from '../../theme/styleTokens';
import { getTagStyle } from '../../utils/tagStyles';
import { sanitizeDescription } from '../../utils/businessLanguage';
import { ENGINE_SVG_SOURCES } from '../../utils/executionRenderers';
import { getEngineIconUrl } from '../../utils/engineIconCache';
import { getItemTypeIcon } from '../../utils/iconHelpers';
import { WorkflowIcon } from '../icons/WorkflowIcon';

const { Text, Paragraph } = Typography;

export interface ActionCardProps {
  action: ActionPreviewData;
  onClick?: () => void;
  /** 'default' = standard, 'preview' = admin preview, 'business' = simplified for business users (Story 7.1). */
  variant?: 'default' | 'preview' | 'business';
  /** When set, shows favorite heart inside the card (catalog only). */
  isFavorite?: boolean;
  /** Called when favorite is toggled; caller should stopPropagation. */
  onToggleFavorite?: (e: MouseEvent) => void;
  /** Hide favorite button when not authenticated. */
  showFavoriteButton?: boolean;
}

/** Story 69.2: Resolve a single engine code to an icon node at given size.
 * Story 31.3: Fallback cascade — 1) icon_url from API cache, 2) ENGINE_SVG_SOURCES hardcoded, 3) iconHelpers. */
function getEngineIconAtSize(engine: string, size: number): ReactNode {
  const apiIconUrl = getEngineIconUrl(engine);
  const svgSrc = apiIconUrl || ENGINE_SVG_SOURCES[engine as ActionEngine];
  if (svgSrc) {
    return (
      <img
        src={svgSrc}
        alt=""
        width={size}
        height={size}
        className="engine-icon-img"
        style={{ flexShrink: 0, width: size, height: size, objectFit: 'contain' }}
        aria-hidden
      />
    );
  }
  const { icon } = getItemTypeIcon('action', engine, { fontSize: size });
  return icon;
}

/** Get engine icon at default card size (40px). */
function getEngineIcon(engine: ActionEngine): ReactNode {
  return getEngineIconAtSize(engine, STYLE_TOKENS.engineIconSize);
}

/** Story 69.2: Display multiple technology icons for workflows with overflow indicator. */
interface TechnologyIconsProps {
  technologies: string[];
  maxVisible?: number;
  iconSize?: number;
}

function TechnologyIcons({ technologies, maxVisible = 3, iconSize = 24 }: TechnologyIconsProps) {
  const visible = technologies.slice(0, maxVisible);
  const overflow = technologies.length - maxVisible;

  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }} data-testid="technology-icons">
      {visible.map((tech, i) => (
        <span key={`${tech}-${i}`} style={{ display: 'inline-flex', flexShrink: 0 }}>
          {getEngineIconAtSize(tech, iconSize)}
        </span>
      ))}
      {overflow > 0 && (
        <span
          data-testid="technology-overflow"
          aria-label={`et ${overflow} technologie${overflow > 1 ? 's' : ''} supplémentaire${overflow > 1 ? 's' : ''}`}
          style={{
            fontSize: 11,
            fontWeight: 600,
            color: 'inherit',
            opacity: 0.55,
            marginLeft: 2,
          }}
        >
          +{overflow}
        </span>
      )}
    </span>
  );
}

/** Story 69.3: Display included action names with engine icons for workflow cards. */
interface IncludedActionsSummaryProps {
  actions: IncludedAction[];
  maxVisible?: number;
}

function IncludedActionsSummary({ actions, maxVisible = 2 }: IncludedActionsSummaryProps) {
  const visible = actions.slice(0, maxVisible);
  const overflow = actions.length - maxVisible;

  return (
    <div
      data-testid="included-actions-summary"
      aria-label="Actions incluses dans le workflow"
      style={{ color: 'inherit' }}
    >
      <Text type="secondary" style={{ fontSize: 12 }}>
        {'Actions : '}
        {visible.map((a, i) => (
          <span key={a.id} style={{ whiteSpace: 'nowrap' }}>
            {a.engine ? (
              <span style={{ display: 'inline-flex', verticalAlign: 'middle', marginRight: 2 }}>
                {getEngineIconAtSize(a.engine, 14)}
              </span>
            ) : null}
            {a.name}
            {i < visible.length - 1 ? ', ' : ''}
          </span>
        ))}
        {overflow > 0 && (
          <span>{` et ${overflow} autre${overflow > 1 ? 's' : ''}`}</span>
        )}
      </Text>
    </div>
  );
}

const MAX_VISIBLE_TAGS = 3;

export const ActionCard = memo(function ActionCard({
  action,
  onClick,
  variant = 'default',
  isFavorite,
  onToggleFavorite,
  showFavoriteButton,
}: ActionCardProps) {
  const { effectiveMode } = useTheme();
  const isDark = effectiveMode === 'dark';
  const { isBusinessProfile } = useAuth();
  const isPreview = variant === 'preview';
  const isBusiness = variant === 'business' || isBusinessProfile;
  const isClickable = !!onClick && !isPreview;
  const isCtaVisible = !isPreview; // AC 2 Story 46.1: CTA visible même sans onClick (disabled si pas d'onClick)
  const isWorkflow = action.item_type === 'workflow';

  // Story 46.1: action incomplète = pas de description ET pas de tags
  const isIncomplete = !action.description && (!action.tags || action.tags.length === 0);

  // Story 7.1 AC2: Sanitize description for business users
  const displayDescription = isBusiness
    ? sanitizeDescription(action.description)
    : action.description;

  // Story 69.3: Extract included actions for workflow cards
  const includedActions = action.included_actions ?? [];

  // Story 69.2: For workflows with technologies, show multiple tech icons; fallback to single engine icon
  // Story 5.7, AC3; Story 18.2: Use shared iconHelpers for workflow, engine-specific SVG for actions
  const workflowTechnologies = action.technologies?.filter((t) => t && t.trim() !== '') || [];
  const icon = isWorkflow && workflowTechnologies.length > 0
    ? <TechnologyIcons technologies={workflowTechnologies} maxVisible={3} iconSize={24} />
    : isWorkflow
      ? getItemTypeIcon('workflow', null, { withTooltip: true, fontSize: STYLE_TOKENS.engineIconSize }).icon
      : (action.engine ? getEngineIcon(action.engine) : null);

  const visibleTags = action.tags?.slice(0, MAX_VISIBLE_TAGS) || [];
  const hiddenTagsCount = (action.tags?.length || 0) - MAX_VISIBLE_TAGS;
  const impactLabel = action.impact_level ? IMPACT_LABELS[action.impact_level] : null;
  const itemTypeLabel = isWorkflow ? 'Workflow' : 'Action';
  const ariaLabel = impactLabel
    ? `${itemTypeLabel}: ${action.name || 'Sans nom'}, impact ${impactLabel}`
    : `${itemTypeLabel}: ${action.name || 'Sans nom'}`;

  const handleKeyDown = (e: KeyboardEvent) => {
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
        position: 'relative',
      }}
      styles={{
        body: {
          padding: STYLE_TOKENS.cardBodyPadding,
          ...(isWorkflow ? { paddingBottom: STYLE_TOKENS.cardBodyPadding + 24 } : undefined),
        },
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
          {/* Badge "Incomplet" — Story 46.1 */}
          {isIncomplete && !isPreview && (
            <Tag color="warning" style={{ margin: 0, fontSize: 11 }}>Incomplet</Tag>
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

        {/* Story 69.3: Included actions summary for workflows */}
        {isWorkflow && includedActions.length > 0 && (
          <IncludedActionsSummary actions={includedActions} maxVisible={2} />
        )}

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
        {/* CTA explicite — affordance (Story 46.1) */}
        {/* AC 2: visible en variant default/business, désactivé si pas d'onClick */}
        {isCtaVisible && (
          <div style={{ marginTop: 8 }}>
            <Button
              type="default"
              size="small"
              disabled={!isClickable}
              onClick={(e) => {
                e.stopPropagation();
                onClick?.();
              }}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') e.stopPropagation();
              }}
              aria-label={
                isBusiness
                  ? `Exécuter ${action.name || 'cette action'}`
                  : `Voir les détails de ${action.name || 'cette action'}`
              }
              style={{ width: '100%' }}
            >
              {isBusiness ? 'Exécuter' : 'Voir les détails'}
            </Button>
          </div>
        )}
      </Space>
      {/* Story 69.2: Workflow indicator — bottom left (AC3, AC4) */}
      {isWorkflow && (
        <div style={{ position: 'absolute', bottom: 8, left: 8 }} data-testid="workflow-indicator">
          <WorkflowIcon size={16} aria-label="Workflow" />
        </div>
      )}
    </Card>
  );
});

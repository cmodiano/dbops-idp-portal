/**
 * ActionCard - Reusable card component for catalog actions (Story 2.5, AC #1, #2).
 *
 * Used in:
 * - Admin preview (Epic 2) with variant='preview'
 * - Catalog listing (Epic 3) with variant='default'
 *
 * Features:
 * - Engine icon (Oracle, SQL Server, DB2)
 * - Title (1 line, truncated)
 * - Description (2 lines, truncated)
 * - ImpactIndicator (triple coding)
 * - Tags (max 3 visible + "+N more")
 * - Hover effect (default variant only)
 * - Keyboard accessible (focusable, Enter to activate)
 */

import { Card, Tag, Typography, Space, Tooltip } from 'antd';
import {
  DatabaseOutlined,
  CloudServerOutlined,
  HddOutlined,
} from '@ant-design/icons';
import type { ActionPreviewData, ActionEngine } from '../../types/api';
import { ImpactIndicator, IMPACT_LABELS } from '../shared/ImpactIndicator';
import { STYLE_TOKENS } from '../../theme/styleTokens';

const { Text, Paragraph } = Typography;

export interface ActionCardProps {
  action: ActionPreviewData;
  onClick?: () => void;
  variant?: 'default' | 'preview';
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

const MAX_VISIBLE_TAGS = 3;

export function ActionCard({ action, onClick, variant = 'default' }: ActionCardProps) {
  const isPreview = variant === 'preview';
  const isClickable = !!onClick && !isPreview;

  const engineIcon = action.engine ? ENGINE_ICONS[action.engine] : null;
  const visibleTags = action.tags?.slice(0, MAX_VISIBLE_TAGS) || [];
  const hiddenTagsCount = (action.tags?.length || 0) - MAX_VISIBLE_TAGS;
  const impactLabel = action.impact_level ? IMPACT_LABELS[action.impact_level] : null;
  const ariaLabel = impactLabel
    ? `Action: ${action.name || 'Sans nom'}, impact ${impactLabel}`
    : `Action: ${action.name || 'Sans nom'}`;

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
      }}
      styles={{
        body: { padding: STYLE_TOKENS.cardBodyPadding },
      }}
    >
      <Space orientation="vertical" size="small" style={{ width: '100%' }}>
        {/* Header: Engine icon + Impact indicator */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            {engineIcon}
            <Text strong style={{ fontSize: 16 }} ellipsis={{ tooltip: action.name }}>
              {action.name || 'Sans nom'}
            </Text>
          </div>
          {action.impact_level && (
            <ImpactIndicator level={action.impact_level} size="small" />
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

        {/* Tags */}
        {visibleTags.length > 0 && (
          <Space size={4} wrap style={{ width: '100%' }}>
            {visibleTags.map((tag) => (
              <Tag key={tag} style={{ margin: 0 }}>
                {tag}
              </Tag>
            ))}
            {hiddenTagsCount > 0 && (
              <Tooltip title={action.tags?.slice(MAX_VISIBLE_TAGS).join(', ')}>
                <Tag style={{ margin: 0 }}>+{hiddenTagsCount}</Tag>
              </Tooltip>
            )}
          </Space>
        )}

        {/* Execution count (si disponible, Task 1.1) */}
        {typeof action.execution_count === 'number' && action.execution_count >= 0 && (
          <Text type="secondary" style={{ fontSize: 12 }}>
            {action.execution_count} exécution{action.execution_count !== 1 ? 's' : ''}
          </Text>
        )}
      </Space>
    </Card>
  );
}

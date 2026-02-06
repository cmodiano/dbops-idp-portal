/**
 * Execution renderers - Reusable utilities for rendering execution table columns (Story 9.9).
 *
 * Extracted from RecentExecutions.tsx for reuse across:
 * - ExecutionsPage.tsx (main executions table)
 * - RecentExecutions.tsx (dashboard widget)
 *
 * AC8: Same mapping engine → icon + color, same integration → Avatar, same tooltips/fallbacks.
 */

import { Badge, Tooltip, Avatar } from 'antd';
import {
  DatabaseOutlined,
  CloudServerOutlined,
  HddOutlined,
  ApartmentOutlined,
  ApiOutlined,
  RocketOutlined,
  ThunderboltOutlined,
  CloudOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  ClockCircleOutlined,
  SyncOutlined,
  PauseCircleOutlined,
  StopOutlined,
  MinusCircleOutlined,
} from '@ant-design/icons';
import type { ActionEngine, ActionPlatform, ItemType, ExecutionStatusType } from '../types/api';
import { STYLE_TOKENS } from '../theme/styleTokens';
import { getIconUrl } from './iconUrl';

/** Engine icon size in execution tables (px) - smaller than ActionCard for table context. */
const ENGINE_ICON_SIZE = 20;

/** SVG paths for database engine icons (real vendor-style icons). */
const ENGINE_SVG_SOURCES: Partial<Record<ActionEngine, string>> = {
  Oracle: '/icons/engines/oracle.svg',
  'SQL Server': '/icons/engines/sqlserver.svg',
  DB2: '/icons/engines/db2.svg',
};

/** Engine icons mapping: engine name → Icon component + color (Story 9.9 AC4). Fallback when SVG not used. */
const ENGINE_ICONS: Record<ActionEngine, { Icon: React.ComponentType<{ style?: React.CSSProperties }>; color: string }> = {
  Oracle: { Icon: DatabaseOutlined, color: STYLE_TOKENS.engineIconColor.Oracle },
  'SQL Server': { Icon: CloudServerOutlined, color: STYLE_TOKENS.engineIconColor['SQL Server'] },
  DB2: { Icon: HddOutlined, color: STYLE_TOKENS.engineIconColor.DB2 },
};

/** Workflow icon color (violet). */
const WORKFLOW_ICON_COLOR = '#722ed1';

/** Platform (execution) icons: platform name → Icon + color. Action.platform is mandatory for actions. */
const PLATFORM_ICONS: Record<ActionPlatform, { Icon: React.ComponentType<{ style?: React.CSSProperties }>; color: string }> = {
  AAP: { Icon: RocketOutlined, color: STYLE_TOKENS.platformIconColor.AAP },
  'GitHub Actions': { Icon: ThunderboltOutlined, color: STYLE_TOKENS.platformIconColor['GitHub Actions'] },
  'Azure DevOps': { Icon: CloudOutlined, color: STYLE_TOKENS.platformIconColor['Azure DevOps'] },
  Terraform: { Icon: ApartmentOutlined, color: STYLE_TOKENS.platformIconColor.Terraform },
};

/**
 * Render execution platform icon for Plateforme column (AC5).
 * Uses action.platform (mandatory for actions) — distinct from integration, which may not be a platform.
 *
 * @param platform - Execution platform from Action (AAP, GitHub Actions, Azure DevOps, Terraform)
 */
export function renderPlatformIcon(platform: ActionPlatform | string | null | undefined): React.ReactNode {
  if (!platform) {
    return <span style={{ color: '#d9d9d9' }}>—</span>;
  }

  const config = PLATFORM_ICONS[platform as ActionPlatform];
  if (!config) {
    return (
      <Tooltip title={platform}>
        <span title={platform} style={{ fontSize: 12, opacity: 0.6 }}>{platform}</span>
      </Tooltip>
    );
  }

  return (
    <Tooltip title={platform}>
      <config.Icon style={{ fontSize: ENGINE_ICON_SIZE, color: config.color }} />
    </Tooltip>
  );
}

/** Map integration name or type → icon URL. Used as fallback when execution has no integration_icon. */
export type IntegrationIconsMap = Record<string, string | null | undefined>;

/**
 * Render Plateforme column icon (AC5).
 * Prefers integration icon when defined; otherwise falls back to integrationIconsMap (from integrations list)
 * when provided, then to execution platform icon.
 *
 * @param integrationName - Integration name (from action.integration)
 * @param integrationIcon - Integration icon URL (user-defined in integration)
 * @param platform - Execution platform from Action (fallback when no integration icon)
 * @param integrationIconsMap - Optional map name/type → icon URL (from GET /admin/integrations) for fallback
 */
export function renderPlateformeIcon(
  integrationName: string | null | undefined,
  integrationIcon: string | null | undefined,
  platform?: ActionPlatform | string | null,
  integrationIconsMap?: IntegrationIconsMap | null,
): React.ReactNode {
  // Prefer integration icon when available (user-defined in integration)
  const iconFromApi = getIconUrl(integrationIcon);
  if (iconFromApi) {
    return renderIntegrationIcon(integrationName, integrationIcon, platform);
  }
  // Fallback: look up in integrationIconsMap by integration name or platform (matches integration page)
  if (integrationIconsMap) {
    const fallbackIcon = (integrationName && getIconUrl(integrationIconsMap[integrationName]))
      || (platform && getIconUrl(integrationIconsMap[platform]));
    if (fallbackIcon) {
      const label = integrationName || platform;
      return (
        <Tooltip title={label ?? undefined}>
          <Avatar
            src={fallbackIcon}
            shape="square"
            size={ENGINE_ICON_SIZE}
            icon={<ApiOutlined />}
            style={{ flexShrink: 0 }}
          />
        </Tooltip>
      );
    }
  }
  return renderPlatformIcon(platform);
}

/**
 * Render engine icon for Technologie column (AC4).
 *
 * @param engine - Engine name (Oracle, SQL Server, DB2) or null
 * @param itemType - Item type (action or workflow)
 * @returns React node with icon + tooltip
 */
export function renderEngineIcon(
  engine: ActionEngine | null | undefined,
  itemType: ItemType | undefined,
): React.ReactNode {
  // Workflow takes priority over engine
  if (itemType === 'workflow') {
    return (
      <Tooltip title="Workflow (chaîne d'actions)">
        <ApartmentOutlined style={{ fontSize: ENGINE_ICON_SIZE, color: WORKFLOW_ICON_COLOR }} />
      </Tooltip>
    );
  }

  // No engine - fallback
  if (!engine) {
    return <span style={{ color: '#d9d9d9' }}>—</span>;
  }

  // Known engine
  const config = ENGINE_ICONS[engine as ActionEngine];
  const svgSrc = ENGINE_SVG_SOURCES[engine as ActionEngine];
  if (!config) {
    // Unknown engine - show text
    return <span title={engine} style={{ fontSize: 12, opacity: 0.6 }}>{engine}</span>;
  }

  if (svgSrc) {
    return (
      <Tooltip title={engine}>
        <img
          src={svgSrc}
          alt=""
          width={ENGINE_ICON_SIZE}
          height={ENGINE_ICON_SIZE}
          style={{ flexShrink: 0, verticalAlign: 'middle' }}
          aria-hidden
        />
      </Tooltip>
    );
  }
  return (
    <Tooltip title={engine}>
      <config.Icon style={{ fontSize: ENGINE_ICON_SIZE, color: config.color }} />
    </Tooltip>
  );
}

/**
 * Render integration icon for Plateforme column (AC5).
 * Uses integration when available, falls back to action.platform when integration is null.
 *
 * @param integrationName - Integration name for tooltip (from INTEGRATIONS)
 * @param integrationIcon - Integration icon URL (from INTEGRATIONS.ICON)
 * @param platform - Action platform (AAP, GitHub Actions, etc.) - fallback when no integration
 */
export function renderIntegrationIcon(
  integrationName: string | null | undefined,
  integrationIcon: string | null | undefined,
  platform?: string | null,
): React.ReactNode {
  const label = integrationName || platform;
  if (!label) {
    return <span style={{ color: '#d9d9d9' }}>—</span>;
  }

  const iconSrc = getIconUrl(integrationIcon);

  return (
    <Tooltip title={label}>
      <Avatar
        src={iconSrc}
        shape="square"
        size={ENGINE_ICON_SIZE}
        icon={<ApiOutlined />}
        style={{ flexShrink: 0 }}
      />
    </Tooltip>
  );
}

/** Status badge configuration for status indicator (AC2, AC3).
 * - processing: Pulsing animation for running states
 * - success/error/default/warning: Fixed color for terminal states
 */
const STATUS_BADGE_CONFIG: Record<
  ExecutionStatusType,
  { status: 'processing' | 'success' | 'error' | 'default' | 'warning'; label: string }
> = {
  SUBMITTED: { status: 'processing', label: 'Soumise' },
  PENDING_APPROVAL: { status: 'processing', label: 'En attente' },
  RUNNING: { status: 'processing', label: 'En cours' },
  COMPLETED: { status: 'success', label: 'Terminée' },
  FAILED: { status: 'error', label: 'Échouée' },
  CANCELLED: { status: 'default', label: 'Annulée' },
  REJECTED: { status: 'warning', label: 'Rejetée' },
};

/**
 * Render status indicator badge for Statut column (AC1, AC2, AC3).
 *
 * - Running states (SUBMITTED, PENDING_APPROVAL, RUNNING): Pulsing blue badge (12-16px)
 * - Terminal states (COMPLETED, FAILED, CANCELLED, REJECTED): Fixed colored badge (10-12px)
 *
 * @param status - Execution status
 * @returns React node with Badge + tooltip
 */
export function renderStatusIndicator(status: ExecutionStatusType): React.ReactNode {
  const config = STATUS_BADGE_CONFIG[status] || { status: 'default' as const, label: 'Inconnu' };
  const isRunning = config.status === 'processing';

  return (
    <Tooltip title={config.label}>
      <Badge
        status={config.status}
        style={{
          transform: isRunning ? 'scale(1.4)' : 'scale(1.2)',
          display: 'inline-block',
        }}
      />
    </Tooltip>
  );
}

/** Status config with icons for RecentExecutions component (legacy compatibility).
 * Includes Icon component for full status display with text. */
export const STATUS_CONFIG: Record<
  ExecutionStatusType,
  { label: string; Icon: React.ComponentType<{ spin?: boolean; style?: React.CSSProperties }>; color: string }
> = {
  SUBMITTED: { label: 'Soumise', Icon: ClockCircleOutlined, color: '#3B82F6' },
  PENDING_APPROVAL: { label: 'En attente', Icon: PauseCircleOutlined, color: '#F59E0B' },
  RUNNING: { label: 'En cours', Icon: SyncOutlined, color: '#3B82F6' },
  COMPLETED: { label: 'Terminée', Icon: CheckCircleOutlined, color: '#10B981' },
  FAILED: { label: 'Échouée', Icon: CloseCircleOutlined, color: '#EF4444' },
  CANCELLED: { label: 'Annulée', Icon: StopOutlined, color: '#9CA3AF' },
  REJECTED: { label: 'Rejetée', Icon: MinusCircleOutlined, color: '#F59E0B' },
};

/** Engine icons config for RecentExecutions component (legacy compatibility). */
export const ENGINE_ICONS_CONFIG = ENGINE_ICONS;
/** Engine SVG sources for custom icons (Oracle, SQL Server, DB2). */
export { ENGINE_SVG_SOURCES };
/** Platform icons config for tests. */
export const PLATFORM_ICONS_CONFIG = PLATFORM_ICONS;
export const ENGINE_ICON_SIZE_VALUE = ENGINE_ICON_SIZE;

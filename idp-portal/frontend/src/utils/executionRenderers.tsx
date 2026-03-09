/**
 * Execution renderers - Reusable utilities for rendering execution table columns (Story 9.9).
 *
 * Extracted from RecentExecutions.tsx for reuse across:
 * - ExecutionsPage.tsx (main executions table)
 * - RecentExecutions.tsx (dashboard widget)
 *
 * AC8: Same mapping engine → icon + color, same integration → Avatar, same tooltips/fallbacks.
 */

/* eslint-disable react-refresh/only-export-components */

import type { CSSProperties } from 'react';
import { Tooltip, Avatar } from 'antd';
import {
  DatabaseOutlined,
  CloudServerOutlined,
  HddOutlined,
  ApartmentOutlined,
  ApiOutlined,
  RocketOutlined,
  ThunderboltOutlined,
  CloudOutlined,
} from '@ant-design/icons';
import { WorkflowIcon } from '../components/icons/WorkflowIcon';
import type { ActionEngine, ActionPlatform, ItemType } from '../types/api';
import { STYLE_TOKENS } from '../theme/styleTokens';
import { useTheme } from '../contexts/ThemeContext';
import { getIconUrl } from './iconUrl';
import { getEngineIconUrl } from './engineIconCache';

/**
 * Returns the fixed badge color for a given environment name (Story 46.3, AC5).
 * Uses STYLE_TOKENS.environmentBadgeColor for consistency — fallback on gray for unknowns.
 *
 * @param env - Environment name (e.g. "production", "staging", "dev")
 */
export function getEnvironmentBadgeColor(env: string | undefined | null): string {
  if (!env) return STYLE_TOKENS.environmentBadgeColor.default;
  const key = env.toLowerCase().replace(/[^a-z]/g, '');
  return (STYLE_TOKENS.environmentBadgeColor as Record<string, string>)[key]
    ?? STYLE_TOKENS.environmentBadgeColor.default;
}

/**
 * Dark-mode-friendly styles for environment Tag (fixes low contrast in dark theme).
 * Uses darker tint background + light text for readability.
 */
export function getEnvironmentTagDarkStyle(env: string | undefined | null): CSSProperties {
  const color = getEnvironmentBadgeColor(env);
  const hex = color.startsWith('#') ? color.slice(1) : null;
  if (!hex || hex.length < 6) {
    // Non-hex color (named color): fall back to a neutral dark-mode tint
    return { color: STYLE_TOKENS.tagTextOnDark };
  }
  const r = parseInt(hex.slice(0, 2), 16);
  const g = parseInt(hex.slice(2, 4), 16);
  const b = parseInt(hex.slice(4, 6), 16);
  return {
    backgroundColor: `rgba(${r}, ${g}, ${b}, 0.35)`,
    color: STYLE_TOKENS.tagTextOnDark,
    borderColor: `rgba(${r}, ${g}, ${b}, 0.5)`,
  };
}

/** Engine icon size in execution tables (px) - clearly visible vendor logos.
 * Increased from 44px to 56px for better visibility and proportion with platform icons.
 */
const ENGINE_ICON_SIZE = 56;

/** Compact icon size for execution tables (Story 17.13) - aligned with size="small" row height. */
const ENGINE_ICON_SIZE_COMPACT = 40;

/** SVG URLs for database engine icons (served from frontend public/icons/engines/). */
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
    return <span style={{ color: STYLE_TOKENS.textMuted }}>—</span>;
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
      <div style={{ display: 'inline-flex', alignItems: 'center', justifyContent: 'center' }}>
        <config.Icon style={{ fontSize: ENGINE_ICON_SIZE_COMPACT, color: config.color }} />
      </div>
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
          <div style={{ display: 'inline-flex', alignItems: 'center', justifyContent: 'center' }}>
            <Avatar
              src={fallbackIcon}
              shape="square"
              size={ENGINE_ICON_SIZE_COMPACT}
              icon={<ApiOutlined />}
              style={{ flexShrink: 0 }}
            />
          </div>
        </Tooltip>
      );
    }
  }
  return renderPlatformIcon(platform);
}

/**
 * Engine icon with SVG on a theme-aware background (Oracle, SQL Server).
 * Light mode: white background for consistency with the page. Dark mode: dark background.
 */
function EngineIconSvgCell({ engine, svgSrc }: { engine: ActionEngine; svgSrc: string }): React.ReactNode {
  const { effectiveMode } = useTheme();
  const isDark = effectiveMode === 'dark';
  const isSqlServer = engine === 'SQL Server';

  const boxStyle: React.CSSProperties = {
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    padding: '6px',
    borderRadius: '4px',
    backgroundColor: isDark ? 'rgba(26, 26, 36, 0.6)' : '#FFFFFF',
    border: isDark ? '1px solid rgba(255, 255, 255, 0.1)' : '1px solid rgba(0, 0, 0, 0.06)',
  };

  const imgFilter = isSqlServer && isDark
    ? 'brightness(0) invert(1) contrast(1.2)' // SQL Server: invert for dark background
    : !isDark && engine === 'Oracle'
      ? 'brightness(1.1) contrast(1.1)' // Oracle on white: slight enhancement
      : 'none';

  return (
    <Tooltip title={engine}>
      <div style={{ display: 'inline-flex', alignItems: 'center', justifyContent: 'center' }}>
        <div style={boxStyle}>
          <img
            src={svgSrc}
            alt=""
            width={ENGINE_ICON_SIZE_COMPACT}
            height={ENGINE_ICON_SIZE_COMPACT}
            className="engine-icon-img"
            style={{ flexShrink: 0, verticalAlign: 'middle', filter: imgFilter, objectFit: 'contain' }}
            aria-hidden
          />
        </div>
      </div>
    </Tooltip>
  );
}

/**
 * Render engine icon for Technologie column (AC4).
 * Story 31.3: Fallback cascade — 1) icon_url from API, 2) ENGINE_SVG_SOURCES hardcoded, 3) ENGINE_ICONS Ant Design.
 *
 * @param engine - Engine name (Oracle, SQL Server, DB2) or null
 * @param itemType - Item type (action or workflow)
 * @param iconUrl - Optional icon_url from API (takes priority over ENGINE_SVG_SOURCES)
 * @returns React node with icon + tooltip
 */
export function renderEngineIcon(
  engine: ActionEngine | null | undefined,
  itemType: ItemType | undefined,
  iconUrl?: string | null,
): React.ReactNode {
  // Workflow takes priority over engine
  if (itemType === 'workflow') {
    return (
      <Tooltip title="Workflow (chaîne d'actions)">
        <div style={{ display: 'inline-flex', alignItems: 'center', justifyContent: 'center' }}>
          <WorkflowIcon fontSize={ENGINE_ICON_SIZE_COMPACT} aria-label="Workflow" />
        </div>
      </Tooltip>
    );
  }

  // No engine - fallback
  if (!engine) {
    return <span style={{ color: STYLE_TOKENS.textMuted }}>—</span>;
  }

  // Known engine
  const config = ENGINE_ICONS[engine as ActionEngine];
  // Story 31.3: Fallback cascade for SVG source
  const apiIconUrl = iconUrl?.trim() || getEngineIconUrl(engine) || undefined;
  const svgSrc = apiIconUrl || ENGINE_SVG_SOURCES[engine as ActionEngine];

  if (!config) {
    // Unknown engine — still try API icon_url before showing text
    if (svgSrc) {
      return (
        <Tooltip title={engine}>
          <div style={{ display: 'inline-flex', alignItems: 'center', justifyContent: 'center' }}>
            <img
              src={svgSrc}
              alt=""
              width={ENGINE_ICON_SIZE_COMPACT}
              height={ENGINE_ICON_SIZE_COMPACT}
              className="engine-icon-img"
              style={{ flexShrink: 0, verticalAlign: 'middle', objectFit: 'contain' }}
              aria-hidden
            />
          </div>
        </Tooltip>
      );
    }
    return <span title={engine} style={{ fontSize: 12, opacity: 0.6 }}>{engine}</span>;
  }

  if (svgSrc) {
    const needsBackground = engine === 'SQL Server' || engine === 'Oracle';
    if (needsBackground) {
      return (
        <EngineIconSvgCell engine={engine} svgSrc={svgSrc} />
      );
    }
    return (
      <Tooltip title={engine}>
        <div style={{ display: 'inline-flex', alignItems: 'center', justifyContent: 'center' }}>
          <img
            src={svgSrc}
            alt=""
            width={ENGINE_ICON_SIZE_COMPACT}
            height={ENGINE_ICON_SIZE_COMPACT}
            style={{ flexShrink: 0, verticalAlign: 'middle' }}
            aria-hidden
          />
        </div>
      </Tooltip>
    );
  }
  return (
    <Tooltip title={engine}>
      <div style={{ display: 'inline-flex', alignItems: 'center', justifyContent: 'center' }}>
        <config.Icon style={{ fontSize: ENGINE_ICON_SIZE_COMPACT, color: config.color }} />
      </div>
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
    return <span style={{ color: STYLE_TOKENS.textMuted }}>—</span>;
  }

  const iconSrc = getIconUrl(integrationIcon);

  return (
    <Tooltip title={label}>
      <div style={{ display: 'inline-flex', alignItems: 'center', justifyContent: 'center' }}>
        <Avatar
          src={iconSrc}
          shape="square"
          size={ENGINE_ICON_SIZE}
          icon={<ApiOutlined />}
          style={{ flexShrink: 0 }}
        />
      </div>
    </Tooltip>
  );
}

/** Engine icons config for RecentExecutions component (legacy compatibility). */
export const ENGINE_ICONS_CONFIG = ENGINE_ICONS;
/** Engine SVG sources for custom icons (Oracle, SQL Server, DB2). */
export { ENGINE_SVG_SOURCES };
/** Platform icons config for tests. */
export const PLATFORM_ICONS_CONFIG = PLATFORM_ICONS;
export const ENGINE_ICON_SIZE_VALUE = ENGINE_ICON_SIZE;
export const ENGINE_ICON_SIZE_COMPACT_VALUE = ENGINE_ICON_SIZE_COMPACT;

// Re-exports pour compatibilité ascendante (consommateurs existants)
export { STATUS_CONFIG, renderStatusIndicator } from './executionStatusRenderer';

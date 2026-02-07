/**
 * iconHelpers - Shared icon utilities for item type (workflow vs action) identification.
 * Story 18.2: Centralized icon logic used by Admin and Catalog components.
 */

import React from 'react';
import {
  ApartmentOutlined,
  DatabaseOutlined,
  CloudServerOutlined,
  HddOutlined,
} from '@ant-design/icons';
import { Tooltip } from 'antd';
import type { ActionEngine, ItemType } from '../types/api';
import { STYLE_TOKENS } from '../theme/styleTokens';

/** Workflow icon color (violet) — sourced from STYLE_TOKENS for consistency. */
export const WORKFLOW_COLOR = STYLE_TOKENS.workflowColor;

/** Result of getItemTypeIcon: icon node, color, and accessible label. */
export interface ItemTypeIconResult {
  icon: React.ReactNode;
  color: string;
  label: string;
}

/**
 * Returns the appropriate icon, color, and label for a given item type and engine.
 * Used by AdminPage and Catalog components for consistent visual identification.
 *
 * @param itemType - 'workflow' or 'action' (or undefined)
 * @param engine - Engine name for actions (Oracle, SQL Server, DB2, etc.)
 * @param options.withTooltip - Wrap icon in Ant Design Tooltip (default: false)
 * @param options.fontSize - Icon font size in px (default: 16)
 */
export function getItemTypeIcon(
  itemType: ItemType | undefined | null,
  engine: ActionEngine | null | undefined,
  options?: { withTooltip?: boolean; fontSize?: number },
): ItemTypeIconResult {
  const fontSize = options?.fontSize ?? 16;
  const withTooltip = options?.withTooltip ?? false;

  if (itemType === 'workflow') {
    const label = "Workflow (chaîne d'actions)";
    const iconNode = (
      <ApartmentOutlined
        style={{ fontSize, color: WORKFLOW_COLOR }}
        aria-label="Type: Workflow"
      />
    );
    return {
      icon: withTooltip ? <Tooltip title={label}>{iconNode}</Tooltip> : iconNode,
      color: WORKFLOW_COLOR,
      label,
    };
  }

  // Action: engine-specific icon
  const engineColors = STYLE_TOKENS.engineIconColor;

  switch (engine) {
    case 'Oracle': {
      const label = 'Action Oracle';
      const iconNode = (
        <DatabaseOutlined
          style={{ fontSize, color: engineColors.Oracle }}
          aria-label="Type: Action Oracle"
        />
      );
      return {
        icon: withTooltip ? <Tooltip title={label}>{iconNode}</Tooltip> : iconNode,
        color: engineColors.Oracle,
        label,
      };
    }
    case 'SQL Server': {
      const label = 'Action SQL Server';
      const iconNode = (
        <CloudServerOutlined
          style={{ fontSize, color: engineColors['SQL Server'] }}
          aria-label="Type: Action SQL Server"
        />
      );
      return {
        icon: withTooltip ? <Tooltip title={label}>{iconNode}</Tooltip> : iconNode,
        color: engineColors['SQL Server'],
        label,
      };
    }
    case 'DB2': {
      const label = 'Action DB2';
      const iconNode = (
        <HddOutlined
          style={{ fontSize, color: engineColors.DB2 }}
          aria-label="Type: Action DB2"
        />
      );
      return {
        icon: withTooltip ? <Tooltip title={label}>{iconNode}</Tooltip> : iconNode,
        color: engineColors.DB2,
        label,
      };
    }
    default: {
      const engineName = engine || 'inconnu';
      const label = `Action ${engineName}`;
      const iconNode = (
        <HddOutlined
          style={{ fontSize, color: '#8c8c8c' }}
          aria-label={`Type: Action ${engineName}`}
        />
      );
      return {
        icon: withTooltip ? <Tooltip title={label}>{iconNode}</Tooltip> : iconNode,
        color: '#8c8c8c',
        label,
      };
    }
  }
}

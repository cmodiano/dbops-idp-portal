/**
 * ActionPalette — Sidebar with draggable published actions for the visual workflow builder (Story 16.5, AC1-AC2).
 *
 * Actions are loaded via useEligibleActions hook (DIP pattern, Story 48.8, AC1).
 */

import React, { useState } from 'react';
import { Input, Spin, Alert, Typography, theme } from 'antd';
import { SearchOutlined } from '@ant-design/icons';
import type { ActionListItem } from '../../types/api';
import { useEligibleActions } from '../../hooks/useEligibleActions';

const { Text } = Typography;

export interface ActionPaletteProps {
  disabled?: boolean;
}

export const ActionPalette: React.FC<ActionPaletteProps> = ({ disabled = false }) => {
  const { token } = theme.useToken();
  const { eligibleActions, loadingActions, loadError } = useEligibleActions();
  const [search, setSearch] = useState('');

  const filtered = search
    ? eligibleActions.filter(
        (a) =>
          a.name.toLowerCase().includes(search.toLowerCase()) ||
          (a.engine ?? '').toLowerCase().includes(search.toLowerCase())
      )
    : eligibleActions;

  const onDragStart = (event: React.DragEvent, action: ActionListItem) => {
    if (disabled) return;
    event.dataTransfer.setData('application/workflow-action', JSON.stringify(action));
    event.dataTransfer.effectAllowed = 'move';
  };

  return (
    <div
      style={{
        width: 220,
        borderRight: `1px solid ${token.colorBorderSecondary}`,
        padding: 12,
        display: 'flex',
        flexDirection: 'column',
        height: '100%',
        overflow: 'hidden',
      }}
    >
      <Text strong style={{ marginBottom: 8, display: 'block' }}>
        Actions disponibles
      </Text>
      <Input
        size="small"
        placeholder="Rechercher..."
        prefix={<SearchOutlined />}
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        style={{ marginBottom: 8 }}
        allowClear
        aria-label="Rechercher une action"
        disabled={disabled}
      />

      <div style={{ flex: 1, overflowY: 'auto' }}>
        {loadingActions && (
          <div style={{ textAlign: 'center', padding: 16 }}>
            <Spin size="small" />
          </div>
        )}
        {loadError && <Alert type="error" title={loadError} showIcon />}
        {!loadingActions && !loadError && filtered.length === 0 && (
          <Text type="secondary" style={{ fontSize: 12 }}>
            Aucune action disponible
          </Text>
        )}
        {filtered.map((action) => (
          <div
            key={action.id}
            draggable={!disabled}
            onDragStart={(e) => onDragStart(e, action)}
            style={{
              padding: '8px 10px',
              marginBottom: 4,
              border: `1px solid ${token.colorBorderSecondary}`,
              borderRadius: 6,
              background: token.colorBgContainer,
              cursor: disabled ? 'default' : 'grab',
              fontSize: 12,
              opacity: disabled ? 0.5 : 1,
            }}
            aria-label={`Glisser l'action ${action.name} vers le canvas`}
          >
            <div style={{ fontWeight: 500 }}>{action.name}</div>
            {action.engine && (
              <div style={{ fontSize: 11, color: token.colorTextTertiary }}>{action.engine}</div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
};

export default ActionPalette;

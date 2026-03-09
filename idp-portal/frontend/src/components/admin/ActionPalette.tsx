/**
 * ActionPalette — Sidebar with draggable published actions and special step types (Story 16.5, AC1-AC2; Story 57.13).
 *
 * Story 57.13: Restructured into two sections:
 * 1. Platform actions (grouped by category, draggable)
 * 2. Special steps (service_call, evaluation, gate, http_request — click to add)
 *
 * Actions are loaded via useEligibleActions hook (DIP pattern, Story 48.8, AC1).
 */

import { useMemo, useState } from 'react';
import type { FC, ReactNode } from 'react';
import { Button, Collapse, Input, Spin, Alert, Tag, Typography, theme } from 'antd';
import {
  SearchOutlined,
  ApiOutlined,
  SafetyCertificateOutlined,
  ClockCircleOutlined,
  GlobalOutlined,
  ScheduleOutlined,
} from '@ant-design/icons';
import type { ActionListItem } from '../../types/api';
import type { WorkflowStepType } from '../../types/api';
import { useEligibleActions } from '../../hooks/useEligibleActions';

const { Text } = Typography;

// Story 57.13: Special step types colors and labels
const SPECIAL_STEP_TYPES: {
  type: WorkflowStepType;
  label: string;
  color: string;
  icon: ReactNode;
}[] = [
  { type: 'service_call', label: 'Appel service', color: '#fa8c16', icon: <ApiOutlined /> },
  { type: 'evaluation', label: 'Évaluer', color: '#722ed1', icon: <SafetyCertificateOutlined /> },
  { type: 'gate', label: 'Attendre', color: '#faad14', icon: <ClockCircleOutlined /> },
  { type: 'http_request', label: 'Requête HTTP', color: '#13c2c2', icon: <GlobalOutlined /> },
  { type: 'schedule_execution', label: 'Planifier une exécution', color: '#4f46e5', icon: <ScheduleOutlined /> },
];

export interface ActionPaletteProps {
  disabled?: boolean;
  /** Story 57.13: Callback to add a special step type (non-platform) */
  onAddSpecialStep?: (stepType: WorkflowStepType) => void;
}

export const ActionPalette: FC<ActionPaletteProps> = ({
  disabled = false,
  onAddSpecialStep,
}) => {
  const { token } = theme.useToken();
  const { eligibleActions, loadingActions, loadError } = useEligibleActions();
  const [search, setSearch] = useState('');

  // Story 57.13: Group platform actions by category
  const groupedActions = useMemo(() => {
    const q = search.toLowerCase();
    const filtered = eligibleActions.filter(
      (a) =>
        a.name.toLowerCase().includes(q) ||
        (a.engine ?? '').toLowerCase().includes(q) ||
        (a.tags ?? []).some((t) => t.toLowerCase().includes(q))
    );
    return filtered.reduce<Record<string, ActionListItem[]>>((acc, action) => {
      const cat = action.category ?? 'Autre';
      if (!acc[cat]) acc[cat] = [];
      acc[cat].push(action);
      return acc;
    }, {});
  }, [eligibleActions, search]);

  const categoryKeys = Object.keys(groupedActions).sort();

  const onDragStart = (event: React.DragEvent, action: ActionListItem) => {
    if (disabled) return;
    event.dataTransfer.setData('application/workflow-action', JSON.stringify(action));
    event.dataTransfer.effectAllowed = 'move';
  };

  return (
    <div
      style={{
        width: 240,
        borderRight: `1px solid ${token.colorBorderSecondary}`,
        padding: 12,
        display: 'flex',
        flexDirection: 'column',
        height: '100%',
        overflow: 'hidden',
      }}
    >
      <Input
        size="small"
        placeholder="Rechercher une action..."
        prefix={<SearchOutlined />}
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        style={{ marginBottom: 8 }}
        allowClear
        aria-label="Rechercher une action"
        disabled={disabled}
      />

      <div style={{ flex: 1, overflowY: 'auto' }}>
        {/* Platform actions grouped by category */}
        <Text
          strong
          style={{
            fontSize: 11,
            display: 'block',
            marginBottom: 6,
            textTransform: 'uppercase',
            color: token.colorTextTertiary,
          }}
        >
          Actions (Exécuter)
        </Text>

        {loadingActions && (
          <div style={{ textAlign: 'center', padding: 16 }}>
            <Spin size="small" />
          </div>
        )}
        {loadError && <Alert type="error" title={loadError} showIcon style={{ marginBottom: 8 }} />}
        {!loadingActions && !loadError && categoryKeys.length === 0 && (
          <Text type="secondary" style={{ fontSize: 12 }}>
            Aucune action disponible
          </Text>
        )}

        {!loadingActions && categoryKeys.length > 0 && (
          <Collapse
            size="small"
            defaultActiveKey={categoryKeys}
            style={{ marginBottom: 12 }}
            items={categoryKeys.map((category) => ({
              key: category,
              label: <Text style={{ fontSize: 11, fontWeight: 600 }}>{category}</Text>,
              children: (
                <div>
                  {groupedActions[category].map((action) => (
                    <div
                      key={action.id}
                      draggable={!disabled}
                      onDragStart={(e) => onDragStart(e, action)}
                      style={{
                        padding: '6px 8px',
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
                      <div
                        style={{
                          fontWeight: 500,
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                          whiteSpace: 'nowrap',
                        }}
                      >
                        {action.name}
                      </div>
                      {action.engine && (
                        <Tag
                          style={{
                            fontSize: 10,
                            lineHeight: '16px',
                            padding: '0 4px',
                            marginTop: 2,
                          }}
                        >
                          {action.engine}
                        </Tag>
                      )}
                    </div>
                  ))}
                </div>
              ),
            }))}
          />
        )}

        {/* Story 57.13: Special steps section */}
        <Text
          strong
          style={{
            fontSize: 11,
            display: 'block',
            marginTop: 4,
            marginBottom: 6,
            textTransform: 'uppercase',
            color: token.colorTextTertiary,
          }}
        >
          Steps spéciaux
        </Text>
        <div>
          {SPECIAL_STEP_TYPES.map(({ type, label, color, icon }) => (
            <Button
              key={type}
              size="small"
              disabled={disabled || !onAddSpecialStep}
              onClick={() => onAddSpecialStep?.(type)}
              style={{
                width: '100%',
                marginBottom: 6,
                textAlign: 'left',
                borderColor: color,
                color: color,
              }}
              icon={icon}
              aria-label={`Ajouter un step ${label}`}
              data-testid={`add-special-step-${type}`}
            >
              {label}
            </Button>
          ))}
        </div>
      </div>
    </div>
  );
};

export default ActionPalette;

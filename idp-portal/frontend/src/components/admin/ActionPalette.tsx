/**
 * ActionPalette — Sidebar with draggable published actions and special step types (Story 16.5, AC1-AC2; Story 57.13).
 *
 * Story 57.13: Restructured into two sections:
 * 1. Platform actions (grouped by category, draggable)
 * 2. Special steps (service_call, evaluation, gate, http_request — click to add)
 *
 * Actions are loaded via useEligibleActions hook (DIP pattern, Story 48.8, AC1).
 *
 * Story 84.3 (AC3/W1): Les special steps dérivent de useCapabilities() plutôt que d'une constante locale.
 * STEP_TYPE_UI_META fournit couleur et icône (concerns UI, non dérivables du backend).
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
import { useCapabilities } from '../../hooks/useCapabilities';

const { Text } = Typography;

// Story 84.3 (AC3): UI-only metadata — couleur et icône par code de step type.
// Non dérivable du backend (décisions UX). Fallback _default pour types inconnus.
const STEP_TYPE_UI_META: Record<string, { color: string; icon: ReactNode }> = {
  service_call:       { color: '#fa8c16', icon: <ApiOutlined /> },
  evaluation:         { color: '#722ed1', icon: <SafetyCertificateOutlined /> },
  gate:               { color: '#faad14', icon: <ClockCircleOutlined /> },
  http_request:       { color: '#13c2c2', icon: <GlobalOutlined /> },
  schedule_execution: { color: '#4f46e5', icon: <ScheduleOutlined /> },
  _default:           { color: '#8c8c8c', icon: <ApiOutlined /> },
};

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
  const { capabilities, loading: loadingCapabilities, error: capabilitiesError } = useCapabilities();
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

  // Story 84.3 (AC3): special steps dérivés des capabilities backend, platform et parallel_group exclus
  const specialSteps = useMemo(() => {
    return (capabilities?.stepTypes ?? []).filter(
      (s) => s.code !== 'platform' && s.code !== 'parallel_group'
    );
  }, [capabilities]);

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

        {/* Story 84.3 (AC3/W1): Special steps section — dérivée des capabilities backend */}
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
          {loadingCapabilities && (
            <div style={{ textAlign: 'center', padding: 8 }}>
              <Spin size="small" />
            </div>
          )}
          {!loadingCapabilities && !capabilitiesError && specialSteps.map((s) => {
            const uiMeta = STEP_TYPE_UI_META[s.code] ?? STEP_TYPE_UI_META._default;
            return (
              <Button
                key={s.code}
                size="small"
                disabled={disabled || !onAddSpecialStep}
                onClick={() => onAddSpecialStep?.(s.code as WorkflowStepType)}
                style={{
                  width: '100%',
                  marginBottom: 6,
                  textAlign: 'left',
                  borderColor: uiMeta.color,
                  color: uiMeta.color,
                }}
                icon={uiMeta.icon}
                aria-label={`Ajouter un step ${s.label}`}
                data-testid={`add-special-step-${s.code}`}
              >
                {s.label}
              </Button>
            );
          })}
        </div>
      </div>
    </div>
  );
};

export default ActionPalette;

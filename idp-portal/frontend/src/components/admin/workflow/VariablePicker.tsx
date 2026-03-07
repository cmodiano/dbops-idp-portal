/**
 * VariablePicker — Sélecteur de variables Jinja2 depuis les schemas de sortie des steps précédents (Story 63.3).
 *
 * Rendu comme un Popover Ant Design déclenché par un bouton icône CodeOutlined.
 * Groupement par step, recherche, tooltip description.
 */

import React, { useState, useMemo } from 'react';
import { Popover, Input, Tooltip, Spin, Empty, Typography, theme } from 'antd';
import { CodeOutlined, ThunderboltOutlined, ApiOutlined, GlobalOutlined } from '@ant-design/icons';
import { useOutputSchemas } from '../../../hooks/useOutputSchemas';

const { Text } = Typography;

const STEP_TYPE_ICONS: Record<string, React.ReactNode> = {
  platform: <ThunderboltOutlined />,
  service_call: <ApiOutlined />,
  http_request: <GlobalOutlined />,
};

export interface VariablePickerProps {
  workflowId: number | undefined;
  currentStepId: string;
  onSelect: (expression: string) => void;
  disabled?: boolean;
  /** Step IDs disponibles (filtrage des steps précédents). */
  availableStepIds?: string[];
}

export const VariablePicker: React.FC<VariablePickerProps> = ({
  workflowId,
  currentStepId,
  onSelect,
  disabled = false,
  availableStepIds,
}) => {
  const [search, setSearch] = useState('');
  const [open, setOpen] = useState(false);
  const [hoveredVar, setHoveredVar] = useState<string | null>(null);
  const { token } = theme.useToken();
  const { availableVariables, loading } = useOutputSchemas(workflowId);

  const filtered = useMemo(() => {
    // Si availableStepIds est fourni, filtrer pour n'inclure que les steps précédents (pas le step courant).
    // Si availableStepIds est undefined, pas de filtrage (montrer tous les steps).
    const precedingIds = availableStepIds != null
      ? availableStepIds.filter((id) => id !== currentStepId)
      : null;
    return availableVariables
      .filter((step) => precedingIds == null || precedingIds.includes(step.step_id))
      .map((step) => ({
        ...step,
        variables: step.variables.filter(
          (v) =>
            !search ||
            v.name.toLowerCase().includes(search.toLowerCase()) ||
            (v.description ?? '').toLowerCase().includes(search.toLowerCase()),
        ),
      }))
      .filter((step) => step.variables.length > 0);
  }, [availableVariables, availableStepIds, currentStepId, search]);

  const content = (
    <div style={{ width: 300, maxHeight: 400, overflowY: 'auto' }}>
      <Input
        size="small"
        placeholder="Rechercher une variable..."
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        style={{ marginBottom: 8 }}
      />
      {loading && <Spin size="small" />}
      {!loading && filtered.length === 0 && (
        <Empty description="Aucune variable disponible" image={Empty.PRESENTED_IMAGE_SIMPLE} />
      )}
      {filtered.map((step) => (
        <div key={step.step_id} style={{ marginBottom: 8 }}>
          <Text strong style={{ fontSize: 12, display: 'block', marginBottom: 4 }}>
            {STEP_TYPE_ICONS[step.step_type] ?? null} {step.step_name || step.step_id}
          </Text>
          {step.variables.map((v) => (
            <Tooltip key={v.name} title={`${v.description} (${v.type})`} placement="right">
              <div
                role="button"
                tabIndex={0}
                onClick={() => {
                  onSelect(`{{ steps.${step.step_id}.${v.name} }}`);
                  setOpen(false);
                  setSearch('');
                }}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    onSelect(`{{ steps.${step.step_id}.${v.name} }}`);
                    setOpen(false);
                    setSearch('');
                  }
                }}
                onMouseEnter={() => setHoveredVar(`${step.step_id}-${v.name}`)}
                onMouseLeave={() => setHoveredVar(null)}
                style={{
                  cursor: 'pointer',
                  padding: '2px 8px',
                  borderRadius: 4,
                  fontSize: 12,
                  fontFamily: 'monospace',
                  backgroundColor: hoveredVar === `${step.step_id}-${v.name}` ? token.colorFillSecondary : undefined,
                }}
                data-testid={`variable-option-${step.step_id}-${v.name}`}
              >
                {v.name}
                <Text type="secondary" style={{ fontSize: 11, marginLeft: 6 }}>
                  {v.type}
                </Text>
              </div>
            </Tooltip>
          ))}
        </div>
      ))}
    </div>
  );

  return (
    <Popover
      content={content}
      trigger="click"
      open={open}
      onOpenChange={disabled ? undefined : setOpen}
      placement="bottomRight"
    >
      <CodeOutlined
        style={{
          cursor: disabled ? 'not-allowed' : 'pointer',
          color: disabled ? token.colorTextDisabled : token.colorPrimary,
          marginLeft: 4,
        }}
        aria-label="Sélectionner une variable"
        data-testid="variable-picker-trigger"
        onClick={disabled ? (e) => e.preventDefault() : undefined}
      />
    </Popover>
  );
};

export default VariablePicker;

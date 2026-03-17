/**
 * ExecutionView - Immersive real-time execution view drawer (Story 19.1, 19.2).
 *
 * Opens as a right-side Drawer after execution launch, replacing the simple "Action démarrée" popup.
 * Shows metadata header (AC8), timeline with steps (AC2-5), real-time updates (AC6),
 * close/back button (AC7), error handling (AC9), and action/workflow badge (AC10).
 *
 * Story 19.2: Detects workflow executions (item_type === 'workflow') and renders
 * WorkflowExecutionGraph instead of ExecutionTimeline for visual graph display.
 *
 * Delegates real-time timeline rendering to ExecutionTimeline (Story 4.6, 19.0).
 */

import { useEffect, useCallback, useRef } from 'react';
import { Drawer, Spin, Alert, Button, Space, Badge, Typography, theme } from 'antd';
import { CloseOutlined, ReloadOutlined } from '@ant-design/icons';
import { ExecutionTimeline } from './ExecutionTimeline';
import { WorkflowExecutionGraph } from './WorkflowExecutionGraph';
import { useExecutionView } from '../../hooks/useExecutionView';
import type { ExecutionStatusType, RemediationSuggestion, ActionEngine } from '../../types/api';
import { getItemTypeIcon } from '../../utils/iconHelpers';
import { EXECUTION_STATUS_BADGE_CONFIG } from '../../utils/execution-status';

const { Text, Title } = Typography;

const TERMINAL_STATUSES: ExecutionStatusType[] = ['COMPLETED', 'FAILED', 'CANCELLED', 'REJECTED'];

export interface ExecutionViewProps {
  executionId: number | null;
  onClose: () => void;
  redirectOnClose?: () => void;
  onSuggestionClick?: (suggestion: RemediationSuggestion) => void;
}

/** AC8: Environment badge config. */
const ENV_BADGE: Record<string, { color: string; label: string }> = {
  dev: { color: 'blue', label: 'Développement' },
  staging: { color: 'orange', label: 'Recette' },
  prod: { color: 'red', label: 'Production' },
};


export function ExecutionView({ executionId, onClose, redirectOnClose, onSuggestionClick }: ExecutionViewProps) {
  // Story 38.6: DIP — use hook instead of direct service imports
  const { execution, actionDetail, loading, error, refresh, handleExecutionUpdate } = useExecutionView(executionId);
  const { token } = theme.useToken();
  const closeButtonRef = useRef<HTMLButtonElement>(null);

  // AC1/AC10: Detect type (action simple vs workflow)
  const isWorkflow = execution?.item_type === 'workflow';

  // Story 19.5: Engine-specific icon with tooltip (AC1-5)
  const engine: ActionEngine | null = (execution?.engine as ActionEngine) || null;
  const { icon: typeIcon } = getItemTypeIcon(
    execution?.item_type,
    engine,
    { withTooltip: true, fontSize: 20 },
  );

  // Story 19.4 AC10: Focus management — move focus to close button when drawer opens
  useEffect(() => {
    if (executionId != null && closeButtonRef.current) {
      const timer = setTimeout(() => {
        if (executionId != null && closeButtonRef.current && document.contains(closeButtonRef.current)) {
          closeButtonRef.current.focus();
        }
      }, 350);
      return () => clearTimeout(timer);
    }
  }, [executionId]);

  // AC7: Close and redirect
  const handleClose = useCallback(() => {
    onClose();
    redirectOnClose?.();
  }, [onClose, redirectOnClose]);

  // AC8: Elapsed or total duration
  // NEW-FE-K: Computed once and stored to avoid calling Date.now() twice with different snapshots.
  const duration = (() => {
    if (!execution?.started_at) return null;
    const start = new Date(execution.started_at).getTime();
    const end = execution.completed_at ? new Date(execution.completed_at).getTime() : Date.now();
    const s = Math.floor((end - start) / 1000);
    if (s < 60) return `${s}s`;
    const m = Math.floor(s / 60);
    const r = s % 60;
    return r ? `${m}m ${r}s` : `${m}m`;
  })();

  const envBadge = ENV_BADGE[execution?.environment ?? 'dev'] ?? ENV_BADGE.dev;
  const statusCfg = EXECUTION_STATUS_BADGE_CONFIG[execution?.status ?? 'SUBMITTED'] ?? { color: 'default', label: execution?.status ?? 'SUBMITTED' };
  const isTerminal = execution ? TERMINAL_STATUSES.includes(execution.status) : false;

  return (
    <Drawer
      title={null}
      placement="right"
      open={executionId != null}
      onClose={handleClose}
      closable={false}
      keyboard
      destroyOnHidden
      styles={{
        body: { padding: 0 },
        header: { display: 'none' },
        wrapper: { width: 'min(90vw, 1400px)' },
      }}
      data-testid="execution-view-drawer"
      aria-label="Vue d'exécution temps réel"
    >
      {/* Story 19.4 AC10: aria-live for status announcements */}
      <div
        aria-live="polite"
        aria-atomic="true"
        style={{ position: 'absolute', left: '-9999px', width: 1, height: 1, overflow: 'hidden' }}
        data-testid="execution-view-live-region"
      >
        {loading
          ? 'Chargement de l\'exécution en cours'
          : execution
            ? `Exécution #${execution.id} — ${statusCfg.label}`
            : 'Exécution créée, suivi en cours'}
      </div>

      {/* AC8: Metadata header — dark text for contrast on light background */}
      {execution && (
        <div
          style={{
            padding: '16px 24px',
            borderBottom: `1px solid ${token.colorBorderSecondary}`,
            background: token.colorBgLayout,
            color: token.colorText,
            position: 'sticky',
            top: 0,
            zIndex: 1,
          }}
          data-testid="execution-view-header"
        >
          <Space orientation="vertical" size={8} style={{ width: '100%' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <Space size={8} align="center">
                {/* Story 19.5 AC1-5: Engine-specific icon with tooltip */}
                {typeIcon}
                <Title level={4} style={{ margin: 0 }}>
                  {execution.action_name ?? `Exécution #${execution.id}`}
                </Title>
                {/* Story 19.4 AC9: Remediation badge */}
                {execution.parent_execution_id && execution.parent_item_type !== 'workflow' && (
                  <Text type="secondary" style={{ fontSize: 12 }}>
                    Remédiation de #{execution.parent_execution_id}
                  </Text>
                )}
              </Space>
              <Button
                ref={closeButtonRef}
                icon={<CloseOutlined />}
                onClick={handleClose}
                type="text"
                aria-label="Fermer la vue d'exécution"
                data-testid="close-execution-view"
              />
            </div>

            <Space size={16} wrap>
              <Space size={4}>
                <Text type="secondary">ID:</Text>
                <Text strong>#{execution.id}</Text>
              </Space>
              <Space size={4}>
                <Text type="secondary">Environnement:</Text>
                <Badge color={envBadge.color} text={<span style={{ color: token.colorText }}>{envBadge.label}</span>} />
              </Space>
              <Space size={4}>
                <Text type="secondary">Statut:</Text>
                <Badge status={statusCfg.color} text={<span style={{ color: token.colorText }}>{statusCfg.label}</span>} />
              </Space>
              <Space size={4}>
                <Text type="secondary">Initiateur:</Text>
                <Text>{execution.user_display_name ?? `User #${execution.user_id}`}</Text>
              </Space>
              {duration && (
                <Space size={4}>
                  <Text type="secondary">{isTerminal ? 'Durée:' : 'Temps écoulé:'}</Text>
                  <Text>{duration}</Text>
                </Space>
              )}
            </Space>
          </Space>
        </div>
      )}

      {/* Main content */}
      <div style={{ padding: 24 }}>
        {loading && (
          <div style={{ textAlign: 'center', padding: '48px 0' }}>
            <Spin size="large" />
          </div>
        )}

        {/* Story 19.4 AC6: Network error with retry */}
        {error && !loading && (
          <Alert
            type="warning"
            showIcon
            title="Connexion perdue. Tentative de reconnexion..."
            description={error.message}
            action={
              <Button size="small" onClick={refresh} icon={<ReloadOutlined />}>
                Rafraîchir
              </Button>
            }
            style={{ marginBottom: 16 }}
            data-testid="execution-view-error"
          />
        )}

        {/* Story 19.2 AC1: Workflow graph OR action timeline */}
        {executionId != null && !loading && isWorkflow && actionDetail?.workflow_steps ? (
          <WorkflowExecutionGraph
            executionId={executionId}
            workflowSteps={actionDetail.workflow_steps}
            execution={execution}
            onExecutionUpdate={handleExecutionUpdate}
          />
        ) : executionId != null && !loading ? (
          <ExecutionTimeline
            executionId={executionId}
            execution={execution}
            mode="realtime"
            onSuggestionClick={onSuggestionClick}
            workflowSteps={actionDetail?.workflow_steps ?? undefined}
          />
        ) : null}
      </div>
    </Drawer>
  );
}

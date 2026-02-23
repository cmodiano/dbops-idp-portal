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

import { useState, useEffect, useCallback, useRef } from 'react';
import { Drawer, Spin, Alert, Button, Space, Badge, Typography } from 'antd';
import { CloseOutlined, ReloadOutlined } from '@ant-design/icons';
import { ExecutionTimeline } from './ExecutionTimeline';
import { WorkflowExecutionGraph } from './WorkflowExecutionGraph';
import { getExecution } from '../../services/execution_service';
import { fetchCatalogActionById } from '../../services/catalog_service';
import type { ExecutionResponse, ExecutionStatusType, RemediationSuggestion, ActionEngine } from '../../types/api';
import type { CatalogActionDetail } from '../../services/catalog_service';
import { getItemTypeIcon } from '../../utils/iconHelpers';
import { EXECUTION_STATUS_BADGE_CONFIG } from '../../utils/execution-status';
import logger from '../../services/logger';

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
  const [execution, setExecution] = useState<ExecutionResponse | null>(null);
  const [actionDetail, setActionDetail] = useState<CatalogActionDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);
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
      // Ant Design Drawer animation duration: 0.3s (from antd source: motionDurationMid = 0.2s, use 350ms for safety)
      // Only focus if drawer is still open after animation completes
      const timer = setTimeout(() => {
        // Verify drawer still open before focusing (avoid race condition)
        if (executionId != null && closeButtonRef.current && document.contains(closeButtonRef.current)) {
          closeButtonRef.current.focus();
        }
      }, 350);
      return () => clearTimeout(timer);
    }
  }, [executionId]);

  // Initial load + Story 19.2: load workflow details for graph
  useEffect(() => {
    if (executionId == null) {
      setExecution(null);
      setActionDetail(null);
      setLoading(false);
      setError(null);
      return;
    }

    setLoading(true);
    setError(null);
    getExecution(executionId)
      .then(async (data) => {
        setExecution(data);
        setError(null);
        // Story 19.2 AC2: Load workflow definition if this is a workflow execution
        // Use catalog API (accessible to all users) instead of admin API (DBOPS only)
        if (data.item_type === 'workflow' && data.action_id) {
          try {
            const { data: actionDetailData } = await fetchCatalogActionById(data.action_id);
            setActionDetail(actionDetailData);
          } catch (err) {
            logger.warn('ExecutionView: Failed to load workflow details', {
              action_id: data.action_id,
              error: err instanceof Error ? err.message : String(err),
            });
          }
        }
      })
      .catch((err) => {
        setError(err instanceof Error ? err : new Error(String(err)));
      })
      .finally(() => {
        setLoading(false);
      });
  }, [executionId]);

  // AC7: Close and redirect
  const handleClose = useCallback(() => {
    onClose();
    redirectOnClose?.();
  }, [onClose, redirectOnClose]);

  // Sync execution status from WorkflowExecutionGraph polling/WS
  const handleExecutionUpdate = useCallback((updated: ExecutionResponse) => {
    setExecution((prev) => {
      if (!prev) return updated;
      // Only update if status or completed_at changed
      if (prev.status !== updated.status || prev.completed_at !== updated.completed_at) {
        return { ...prev, status: updated.status, completed_at: updated.completed_at, started_at: updated.started_at ?? prev.started_at };
      }
      return prev;
    });
  }, []);

  // AC9: Manual refresh
  const handleRefresh = useCallback(async () => {
    if (executionId == null) return;
    try {
      const data = await getExecution(executionId);
      setExecution(data);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err : new Error(String(err)));
    }
  }, [executionId]);

  // AC8: Elapsed or total duration
  const getDuration = () => {
    if (!execution?.started_at) return null;
    const start = new Date(execution.started_at).getTime();
    const end = execution.completed_at ? new Date(execution.completed_at).getTime() : Date.now();
    const s = Math.floor((end - start) / 1000);
    if (s < 60) return `${s}s`;
    const m = Math.floor(s / 60);
    const r = s % 60;
    return r ? `${m}m ${r}s` : `${m}m`;
  };

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
            borderBottom: '1px solid #E5E7EB',
            background: '#F5F5F5',
            color: '#262626',
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
                <Title level={4} style={{ margin: 0, color: '#262626' }}>
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
                <Text type="secondary" style={{ color: '#595959' }}>ID:</Text>
                <Text strong style={{ color: '#262626' }}>#{execution.id}</Text>
              </Space>
              <Space size={4}>
                <Text type="secondary" style={{ color: '#595959' }}>Environnement:</Text>
                <Badge color={envBadge.color} text={<span style={{ color: '#262626' }}>{envBadge.label}</span>} />
              </Space>
              <Space size={4}>
                <Text type="secondary" style={{ color: '#595959' }}>Statut:</Text>
                <Badge status={statusCfg.color} text={<span style={{ color: '#262626' }}>{statusCfg.label}</span>} />
              </Space>
              <Space size={4}>
                <Text type="secondary" style={{ color: '#595959' }}>Initiateur:</Text>
                <Text style={{ color: '#262626' }}>{execution.user_display_name ?? `User #${execution.user_id}`}</Text>
              </Space>
              {getDuration() && (
                <Space size={4}>
                  <Text type="secondary" style={{ color: '#595959' }}>{isTerminal ? 'Durée:' : 'Temps écoulé:'}</Text>
                  <Text style={{ color: '#262626' }}>{getDuration()}</Text>
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
              <Button size="small" onClick={handleRefresh} icon={<ReloadOutlined />}>
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
          />
        ) : null}
      </div>
    </Drawer>
  );
}

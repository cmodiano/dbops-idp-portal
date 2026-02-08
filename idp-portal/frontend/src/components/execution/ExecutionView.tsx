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

import { useState, useEffect, useCallback } from 'react';
import { Drawer, Spin, Alert, Button, Space, Badge, Typography } from 'antd';
import { CloseOutlined, ReloadOutlined } from '@ant-design/icons';
import { ExecutionTimeline } from './ExecutionTimeline';
import { WorkflowExecutionGraph } from './WorkflowExecutionGraph';
import { getExecution } from '../../services/execution_service';
import { getAction } from '../../services/admin_service';
import type { ExecutionResponse, ExecutionStatusType, RemediationSuggestion, ActionDetail } from '../../types/api';
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

/** AC8: Status badge config. */
const STATUS_CONFIG: Record<ExecutionStatusType, { color: string; label: string }> = {
  SUBMITTED: { color: 'default', label: 'Soumis' },
  RUNNING: { color: 'processing', label: 'En cours' },
  COMPLETED: { color: 'success', label: 'Terminé' },
  FAILED: { color: 'error', label: 'Échoué' },
  CANCELLED: { color: 'default', label: 'Annulé' },
  INTEGRATION_ERROR: { color: 'error', label: 'Erreur intégration' },
  PENDING_APPROVAL: { color: 'warning', label: 'En attente approbation' },
  REJECTED: { color: 'error', label: 'Rejeté' },
};

export function ExecutionView({ executionId, onClose, redirectOnClose, onSuggestionClick }: ExecutionViewProps) {
  const [execution, setExecution] = useState<ExecutionResponse | null>(null);
  const [actionDetail, setActionDetail] = useState<ActionDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  // AC1/AC10: Detect type (action simple vs workflow)
  const isWorkflow = execution?.item_type === 'workflow';

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
        if (data.item_type === 'workflow' && data.action_id) {
          try {
            const detail = await getAction(data.action_id);
            setActionDetail(detail);
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
  const statusCfg = STATUS_CONFIG[execution?.status ?? 'SUBMITTED'];
  const isTerminal = execution ? TERMINAL_STATUSES.includes(execution.status) : false;

  return (
    <Drawer
      title={null}
      placement="right"
      size="large"
      open={executionId != null}
      onClose={handleClose}
      closable={false}
      destroyOnHidden
      styles={{
        body: { padding: 0 },
        header: { display: 'none' },
      }}
      data-testid="execution-view-drawer"
    >
      {/* AC8: Metadata header */}
      {execution && (
        <div
          style={{
            padding: '16px 24px',
            borderBottom: '1px solid #E5E7EB',
            background: '#FAFAFA',
            position: 'sticky',
            top: 0,
            zIndex: 1,
          }}
          data-testid="execution-view-header"
        >
          <Space orientation="vertical" size={8} style={{ width: '100%' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <Space size={8} align="center">
                {/* AC10: Badge type action/workflow */}
                <Badge
                  count={isWorkflow ? 'Workflow' : 'Action'}
                  style={{
                    backgroundColor: isWorkflow ? '#722ed1' : '#10B981',
                  }}
                />
                <Title level={4} style={{ margin: 0 }}>
                  {execution.action_name ?? `Exécution #${execution.id}`}
                </Title>
              </Space>
              <Button
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
                <Badge color={envBadge.color} text={envBadge.label} />
              </Space>
              <Space size={4}>
                <Text type="secondary">Statut:</Text>
                <Badge status={statusCfg.color as 'default' | 'processing' | 'success' | 'error' | 'warning'} text={statusCfg.label} />
              </Space>
              <Space size={4}>
                <Text type="secondary">Initiateur:</Text>
                <Text>{execution.user_display_name ?? `User #${execution.user_id}`}</Text>
              </Space>
              {getDuration() && (
                <Space size={4}>
                  <Text type="secondary">{isTerminal ? 'Durée:' : 'Temps écoulé:'}</Text>
                  <Text>{getDuration()}</Text>
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

        {/* AC9: Network error */}
        {error && !loading && (
          <Alert
            type="warning"
            showIcon
            title="Erreur de chargement"
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

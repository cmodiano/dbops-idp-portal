/**
 * ExecutionStatusBanners — Story 34.12 (SOLID-FE-1)
 *
 * Extracted from ExecutionTimeline.tsx.
 * Renders all 7 status alert/card banners (polling, parent corrective,
 * PENDING_APPROVAL, REJECTED, COMPLETED, auto-remediation failed, auto-remediation in progress).
 */

import { Alert, Card, Space, Tag, Tooltip, Typography } from 'antd';
import { ReloadOutlined, LinkOutlined, ClockCircleOutlined, StopOutlined, WarningOutlined, SyncOutlined, ToolOutlined } from '@ant-design/icons';
import type { ExecutionResponse, ExecutionStepResponse } from '../../../types/api';
import type { AutoRemediationState } from '../../../hooks/useAutoRemediationState';
import { formatDuration } from './utils';
import { formatUtcToLocal } from '../../../utils/dateFormat';
import { getEnvironmentLabel } from '../../../utils/environmentHelpers';
import { getApprovalInfoFromSteps } from '../../../utils/executionHelpers';

const { Text } = Typography;

interface ExecutionStatusBannersProps {
  execution: ExecutionResponse | null;
  isPolling: boolean;
  autoRemediationState: AutoRemediationState;
  steps: ExecutionStepResponse[];
}

export function ExecutionStatusBanners({
  execution,
  isPolling,
  autoRemediationState,
  steps,
}: ExecutionStatusBannersProps) {
  const approvalInfo = getApprovalInfoFromSteps(steps);

  return (
    <>
      {/* Story 19.0, AC8: Polling mode indicator */}
      {isPolling && (
        <Alert
          type="info"
          showIcon
          icon={<ReloadOutlined spin />}
          title="Mode polling activé (dev)"
          closable
          style={{ marginBottom: 16 }}
          data-testid="polling-mode-alert"
        />
      )}

      {/* Story 9.2, Task 18: Alert when this is a remediation (NOT workflow child) */}
      {execution?.parent_execution_id &&
        execution?.parent_item_type !== 'workflow' && (
          <Alert
            type="info"
            showIcon
            icon={<LinkOutlined />}
            title={
              <>
                Cette exécution est une action corrective de l'exécution{' '}
                <a href={`/executions/${execution.parent_execution_id}`}>
                  #{execution.parent_execution_id}
                </a>
              </>
            }
            style={{ marginBottom: 16 }}
            data-testid="parent-execution-alert"
          />
        )}

      {/* Story 7.4 AC1: Bandeau attente approbation */}
      {execution?.status === 'PENDING_APPROVAL' && (
        <Alert
          type="warning"
          showIcon
          icon={<ClockCircleOutlined />}
          title="En attente d'approbation DBA"
          description={
            <>
              Cette exécution nécessite l'approbation d'un DBA avant de pouvoir démarrer.
              <br />
              <Tag color="orange" style={{ marginTop: 8 }}>Environnement : {getEnvironmentLabel(execution.environment ?? '')}</Tag>
            </>
          }
          style={{ marginBottom: 16 }}
        />
      )}

      {/* Story 7.4 AC4: Bandeau refus */}
      {execution?.status === 'REJECTED' && (
        <Alert
          type="error"
          showIcon
          icon={<StopOutlined />}
          title="Exécution refusée"
          description={
            <>
              Cette exécution a été refusée par un DBA.
              {approvalInfo.approvalComment && (
                <>
                  <br />
                  <strong>Motif :</strong> {approvalInfo.approvalComment}
                </>
              )}
              {approvalInfo.approvedAt && (
                <>
                  <br />
                  <Text type="secondary" style={{ fontSize: 12 }}>
                    Refusé le {formatUtcToLocal(approvalInfo.approvedAt)}
                  </Text>
                </>
              )}
            </>
          }
          style={{ marginBottom: 16 }}
        />
      )}

      {/* Story 4.7, AC1: Bandeau succès quand COMPLETED */}
      {execution?.status === 'COMPLETED' && steps.length > 0 && (
        <Alert
          type="success"
          showIcon
          title="Exécution terminée avec succès"
          description={
            <>
              {steps.length} étape{steps.length > 1 ? 's' : ''}
              {execution.started_at && execution.completed_at && (
                <> — Durée : {formatDuration(execution.started_at, execution.completed_at)}</>
              )}
              {' — '}
              <Tooltip title="Bientôt disponible">
                <span style={{ cursor: 'default', color: 'inherit', textDecoration: 'none' }}>Trace d'audit</span>
              </Tooltip>
              {/* Story 71.2: Show approval info from steps (ADR-007) */}
              {approvalInfo.approvedById != null && approvalInfo.approvedAt && (
                <>
                  <br />
                  <Text type="secondary" style={{ fontSize: 12 }}>
                    Approuvé le {formatUtcToLocal(approvalInfo.approvedAt)}
                    {approvalInfo.approvalComment && <> — {approvalInfo.approvalComment}</>}
                  </Text>
                </>
              )}
            </>
          }
          style={{ marginBottom: 16 }}
        />
      )}

      {/* Story 9.3, AC3: Alert when auto-remediation failed (fallback to manual) */}
      {autoRemediationState.failed && (
        <Alert
          type="warning"
          showIcon
          icon={<WarningOutlined />}
          title="Tentative de correction automatique échouée"
          description={
            <>
              {autoRemediationState.failureMessage || "Le système n'a pas pu corriger automatiquement l'erreur."}
              {' '}Veuillez évaluer manuellement les suggestions ci-dessous.
              {autoRemediationState.childExecutionId && (
                <>
                  <br />
                  <a
                    href={`/executions/${autoRemediationState.childExecutionId}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    style={{ fontSize: 12 }}
                  >
                    Voir l'exécution corrective →
                  </a>
                </>
              )}
            </>
          }
          closable
          style={{ marginBottom: 16 }}
          data-testid="auto-remediation-failed-alert"
        />
      )}

      {/* Story 9.3, AC2: Auto-remediation in progress node */}
      {autoRemediationState.inProgress && (
        <Card
          style={{ marginBottom: 16, borderColor: '#1890ff' }}
          title={
            <Space>
              <SyncOutlined spin style={{ color: '#1890ff' }} />
              <span>Auto-remédiation en cours</span>
              <Tag color="blue">AUTOMATIQUE</Tag>
            </Space>
          }
          data-testid="auto-remediation-progress-card"
        >
          <Space orientation="vertical" size="small" style={{ width: '100%' }}>
            <Text>
              <ToolOutlined style={{ marginRight: 8 }} />
              {autoRemediationState.correctiveActionName || 'Action corrective'}
            </Text>
            <Text type="secondary" style={{ fontSize: 12 }}>
              Le système tente de corriger automatiquement l'erreur détectée...
            </Text>
            {autoRemediationState.childExecutionId && (
              <a
                href={`/executions/${autoRemediationState.childExecutionId}`}
                target="_blank"
                rel="noopener noreferrer"
                style={{ fontSize: 12 }}
              >
                Voir exécution corrective →
              </a>
            )}
          </Space>
        </Card>
      )}
    </>
  );
}

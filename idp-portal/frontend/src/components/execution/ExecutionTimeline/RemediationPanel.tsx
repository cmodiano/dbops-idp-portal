/**
 * RemediationPanel — Story 34.12 (SOLID-FE-1)
 *
 * Extracted from ExecutionTimeline.tsx.
 * Renders StructuredErrorCard + remediation context (skeleton + card).
 */

import { Card, Skeleton, Space, Tag, Typography } from 'antd';
import { CheckCircleOutlined, WarningOutlined } from '@ant-design/icons';
import { StructuredErrorCard } from '../StructuredErrorCard';
import type { ExecutionResponse, ExecutionStepResponse, RemediationSuggestion } from '../../../types/api';
import type { RemediationContext } from '../../../types/api/remediation';

const { Text } = Typography;

interface RemediationPanelProps {
  execution: ExecutionResponse | null;
  failedStep: ExecutionStepResponse | undefined;
  executionId?: number | null;
  onRetry?: () => void;
  onContact?: () => void;
  onViewLogs: (stepId: number) => void;
  errorCardVariant?: 'default' | 'business';
  remediationSuggestions?: RemediationSuggestion[] | null;
  suggestionsLoading: boolean;
  onSuggestionClick?: (s: RemediationSuggestion) => void;
  remediationContext: RemediationContext | null;
  remediationLoading: boolean;
}

export function RemediationPanel({
  execution,
  failedStep,
  executionId,
  onRetry,
  onContact,
  onViewLogs,
  errorCardVariant = 'default',
  remediationSuggestions,
  suggestionsLoading,
  onSuggestionClick,
  remediationContext,
  remediationLoading,
}: RemediationPanelProps) {
  return (
    <>
      {/* Story 4.7, AC2: StructuredErrorCard quand FAILED */}
      {execution?.status === 'FAILED' && failedStep && (
        <div style={{ marginBottom: 16 }}>
          <StructuredErrorCard
            quoi={failedStep.step_name}
            pourquoi={failedStep.error_message ?? 'Erreur inconnue'}
            stepId={failedStep.id}
            executionId={executionId ?? undefined}
            onRetry={onRetry}
            onViewLogs={() => onViewLogs(failedStep.id)}
            onContact={onContact}
            variant={errorCardVariant}
            remediationSuggestions={remediationSuggestions ?? undefined}
            suggestionsLoading={suggestionsLoading}
            onSuggestionClick={onSuggestionClick}
          />
        </div>
      )}

      {/* Story 9.2: Loading skeleton for remediation context */}
      {execution?.status === 'FAILED' && remediationLoading && (
        <Card style={{ marginBottom: 16 }} title="Chargement du contexte de remédiation...">
          <Skeleton active />
        </Card>
      )}

      {/* Story 9.2, Task 17: Remediation context card */}
      {execution?.status === 'FAILED' && !remediationLoading && remediationContext?.has_remediation && (
        <Card
          style={{ marginBottom: 16 }}
          title={
            <Space>
              {remediationContext.successful_remediation ? (
                <>
                  <CheckCircleOutlined style={{ color: '#10B981' }} />
                  <span>Actions correctives appliquées</span>
                  <Tag color="success">Corrigé</Tag>
                </>
              ) : (
                <>
                  <WarningOutlined style={{ color: '#F59E0B' }} />
                  <span>Tentatives de correction</span>
                  <Tag color="warning">Échec</Tag>
                </>
              )}
            </Space>
          }
          data-testid="remediation-context-card"
        >
          <Space direction="vertical" style={{ width: '100%' }} size="small">
            {remediationContext.remediation_actions.map((action) => (
              <Card.Grid
                key={action.execution_id}
                style={{ width: '100%', padding: 12 }}
                hoverable={false}
              >
                <Space direction="vertical" size={4} style={{ width: '100%' }}>
                  <Space>
                    <Tag
                      color={
                        action.status === 'COMPLETED'
                          ? 'success'
                          : action.status === 'FAILED'
                          ? 'error'
                          : action.status === 'RUNNING'
                          ? 'processing'
                          : 'default'
                      }
                    >
                      {action.status}
                    </Tag>
                    <Text strong>{action.action_name}</Text>
                  </Space>
                  <Text type="secondary" style={{ fontSize: 12 }}>
                    Démarrée: {new Date(action.created_at).toLocaleString()}
                    {action.completed_at && (
                      <> — Terminée: {new Date(action.completed_at).toLocaleString()}</>
                    )}
                  </Text>
                  <a
                    href={`/executions/${action.execution_id}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    style={{ fontSize: 12 }}
                  >
                    Voir exécution →
                  </a>
                </Space>
              </Card.Grid>
            ))}
          </Space>
        </Card>
      )}
    </>
  );
}

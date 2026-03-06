/**
 * PendingApprovalsList - List of executions pending DBA approval (Story 7.4).
 *
 * AC2: Display pending approvals with action, requester, environment, parameters, created_at.
 * AC6: Approve/Reject buttons with confirmation modal.
 */

import { useState } from 'react';
import { App, Table, Button, Space, Modal, Input, Tag, Typography, Tooltip } from 'antd';
import type { TableProps } from 'antd';
import {
  CheckCircleOutlined,
  CloseCircleOutlined,
  ClockCircleOutlined,
  ExclamationCircleOutlined,
} from '@ant-design/icons';

import type { ExecutionResponse } from '../../types/api';
import { usePendingApprovals } from '../../hooks/usePendingApprovals';
import { getEnvironmentBadgeColor } from '../../utils/executionRenderers';
import { getEnvironmentLabel } from '../../utils/environmentHelpers';
import { STYLE_TOKENS } from '../../theme/styleTokens';
import { humanizeKey, formatParamValue, partitionParameters, ENV_CONFIG_LABELS, IMPACT_LEVEL_LABELS } from './approvalContextUtils';

const { Text } = Typography;
const { TextArea } = Input;

// === ApprovalContext component (Story 58.6, AC4) ===

interface ApprovalContextProps {
  parameters: Record<string, unknown> | null;
  targets?: { target_type: string; target_id: string; target_name: string }[];
  compact?: boolean;
}

function ApprovalContext({ parameters, targets, compact }: ApprovalContextProps) {
  const { targets: paramTargets, envConfig, stepParams, businessParams } = partitionParameters(parameters);

  // Use targets prop (rich objects) first, fallback to _targets from parameters
  const hasRichTargets = targets && targets.length > 0;
  const hasFallbackTargets = !hasRichTargets && paramTargets.length > 0;
  const hasBusinessParams = Object.keys(businessParams).length > 0;
  const hasStepParams = stepParams && Object.keys(stepParams).length > 0;
  const hasEnvConfig = envConfig && Object.keys(envConfig).length > 0;
  const hasAnyContent = hasRichTargets || hasFallbackTargets || hasBusinessParams || hasStepParams || hasEnvConfig;

  if (!hasAnyContent) {
    return <Text type="secondary" style={{ fontStyle: 'italic', fontSize: compact ? 12 : undefined }}>Aucun paramètre</Text>;
  }

  const containerStyle = compact
    ? { fontSize: 12 }
    : { padding: 8, background: '#f5f5f5', borderRadius: 4, fontSize: 12 };

  const formatEnvConfigValue = (key: string, value: unknown): string => {
    if (key === 'impact_level' && typeof value === 'string') {
      return IMPACT_LEVEL_LABELS[value] || humanizeKey(value);
    }
    return formatParamValue(value);
  };

  return (
    <div style={containerStyle}>
      {/* Targets section */}
      {hasRichTargets && (
        <div style={{ marginBottom: 4 }}>
          <Text strong style={{ fontSize: 12 }}>Cibles :</Text>{' '}
          {targets!.map(t => (
            <Tag key={`${t.target_type ?? 'target'}-${t.target_id}`} style={{ marginBottom: 2 }}>{t.target_name || t.target_id}</Tag>
          ))}
        </div>
      )}
      {hasFallbackTargets && (
        <div style={{ marginBottom: 4 }}>
          <Text strong style={{ fontSize: 12 }}>Cibles :</Text>{' '}
          {paramTargets.map(name => (
            <Tag key={name} style={{ marginBottom: 2 }}>{name}</Tag>
          ))}
        </div>
      )}

      {/* Business parameters */}
      {hasBusinessParams && (
        <div style={{ marginBottom: 4 }}>
          <Text strong style={{ fontSize: 12 }}>Paramètres :</Text>
          {Object.entries(businessParams).map(([k, v]) => (
            <div key={k} style={{ fontSize: 12, paddingLeft: compact ? 0 : 8 }}>
              <Text type="secondary">{humanizeKey(k)} :</Text> {formatParamValue(v)}
            </div>
          ))}
        </div>
      )}

      {/* Workflow step parameters */}
      {hasStepParams && (
        <div style={{ marginBottom: 4 }}>
          <Text strong style={{ fontSize: 12 }}>Paramètres par étape :</Text>
          {Object.entries(stepParams!).map(([stepOrder, stepData]) => {
            const params = stepData && typeof stepData === 'object' && 'parameters' in stepData
              ? (stepData as { parameters: Record<string, unknown> }).parameters
              : null;
            return (
            <div key={stepOrder} style={{ fontSize: 12, paddingLeft: compact ? 0 : 8 }}>
              <Text type="secondary">Étape {stepOrder} :</Text>
              {params && Object.entries(params).map(([pk, pv]) => (
                <div key={pk} style={{ paddingLeft: compact ? 8 : 16 }}>
                  {humanizeKey(pk)} : {formatParamValue(pv)}
                </div>
              ))}
            </div>
            );
          })}
        </div>
      )}

      {/* Env config */}
      {hasEnvConfig && (
        <div>
          <Text strong style={{ fontSize: 12 }}>Configuration :</Text>
          {Object.entries(envConfig!).map(([k, v]) => (
            <div key={k} style={{ fontSize: 12, paddingLeft: compact ? 0 : 8 }}>
              <Text type="secondary">{ENV_CONFIG_LABELS[k] || humanizeKey(k)} :</Text> {formatEnvConfigValue(k, v)}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

interface PendingApprovalsListProps {
  executions: ExecutionResponse[];
  loading: boolean;
  onActionComplete: () => void;
}

export function PendingApprovalsList({
  executions,
  loading,
  onActionComplete,
}: PendingApprovalsListProps) {
  const { message } = App.useApp();
  // Story 38.6: DIP — use hook instead of direct service imports
  const { approve, reject, approveLoading, rejectLoading } = usePendingApprovals(onActionComplete);
  const [approveModalOpen, setApproveModalOpen] = useState(false);
  const [rejectModalOpen, setRejectModalOpen] = useState(false);
  const [selectedExecution, setSelectedExecution] = useState<ExecutionResponse | null>(null);
  const [comment, setComment] = useState('');

  const handleApproveClick = (execution: ExecutionResponse) => {
    setSelectedExecution(execution);
    setComment('');
    setApproveModalOpen(true);
  };

  const handleRejectClick = (execution: ExecutionResponse) => {
    setSelectedExecution(execution);
    setComment('');
    setRejectModalOpen(true);
  };

  const handleApproveConfirm = async () => {
    if (!selectedExecution) return;
    const result = await approve(selectedExecution.id, comment || undefined);
    if (result.success) {
      message.success(`Exécution #${selectedExecution.id} approuvée`);
      setApproveModalOpen(false);
    } else {
      message.error(result.error);
    }
  };

  const handleRejectConfirm = async () => {
    if (!selectedExecution) return;
    const result = await reject(selectedExecution.id, comment || undefined);
    if (result.success) {
      message.success(`Exécution #${selectedExecution.id} refusée`);
      setRejectModalOpen(false);
    } else {
      message.error(result.error);
    }
  };

  const columns: TableProps<ExecutionResponse>['columns'] = [
    {
      title: 'Action',
      dataIndex: 'action_name',
      key: 'action_name',
      render: (name: string | null, record: ExecutionResponse) => (
        <Tooltip title={`ID: ${record.action_id}`}>
          <Text strong>{name || `Action #${record.action_id}`}</Text>
        </Tooltip>
      ),
    },
    {
      title: 'Demandeur',
      dataIndex: 'user_display_name',
      key: 'user_display_name',
      render: (displayName: string | null, record: ExecutionResponse) => (
        <Text>{displayName || `Utilisateur #${record.user_id}`}</Text>
      ),
    },
    {
      title: 'Environnement',
      dataIndex: 'environment',
      key: 'environment',
      render: (env: string | null) => (
        <Tag color={getEnvironmentBadgeColor(env)}>
          {getEnvironmentLabel(env ?? '')}
        </Tag>
      ),
    },
    {
      title: 'Contexte',
      key: 'context',
      render: (_: unknown, record: ExecutionResponse) => (
        <Space orientation="vertical" size={2} style={{ fontSize: 12 }}>
          <ApprovalContext parameters={record.parameters} targets={record.targets} compact />
        </Space>
      ),
    },
    {
      title: 'Date de soumission',
      dataIndex: 'created_at',
      key: 'created_at',
      render: (date: string) => (
        <Tooltip title={new Date(date).toLocaleString()}>
          <Space>
            <ClockCircleOutlined />
            {new Date(date).toLocaleDateString()}
          </Space>
        </Tooltip>
      ),
    },
    {
      title: 'Actions',
      key: 'actions',
      render: (_: unknown, record: ExecutionResponse) => (
        <Space>
          <Button
            type="primary"
            icon={<CheckCircleOutlined />}
            size="small"
            onClick={() => handleApproveClick(record)}
            style={{ backgroundColor: STYLE_TOKENS.impactColor.low, borderColor: STYLE_TOKENS.impactColor.low }}
          >
            Approuver
          </Button>
          <Button
            danger
            icon={<CloseCircleOutlined />}
            size="small"
            onClick={() => handleRejectClick(record)}
          >
            Refuser
          </Button>
        </Space>
      ),
    },
  ];

  return (
    <>
      <Table<ExecutionResponse>
        columns={columns}
        dataSource={executions}
        rowKey="id"
        loading={loading}
        pagination={false}
        locale={{ emptyText: 'Aucune approbation en attente' }}
        size="small"
      />

      {/* Approve confirmation modal */}
      <Modal
        title={
          <Space>
            <CheckCircleOutlined style={{ color: STYLE_TOKENS.impactColor.low }} />
            Confirmer l'approbation
          </Space>
        }
        open={approveModalOpen}
        onCancel={() => setApproveModalOpen(false)}
        onOk={handleApproveConfirm}
        confirmLoading={approveLoading}
        okText="Approuver"
        okButtonProps={{ style: { backgroundColor: STYLE_TOKENS.impactColor.low, borderColor: STYLE_TOKENS.impactColor.low } }}
        cancelText="Annuler"
      >
        {selectedExecution && (
          <div style={{ marginBottom: 16 }}>
            <p>
              Vous êtes sur le point d'approuver l'exécution de{' '}
              <strong>{selectedExecution.action_name || `Action #${selectedExecution.action_id}`}</strong>{' '}
              en environnement <Tag color={getEnvironmentBadgeColor(selectedExecution.environment)}>{getEnvironmentLabel(selectedExecution.environment ?? '')}</Tag>
            </p>
            <p style={{ color: '#666', fontSize: 13 }}>
              L'exécution sera lancée immédiatement après approbation.
            </p>
            <ApprovalContext parameters={selectedExecution.parameters} targets={selectedExecution.targets} />
          </div>
        )}
        <TextArea
          placeholder="Commentaire (optionnel)"
          value={comment}
          onChange={(e) => setComment(e.target.value)}
          rows={3}
        />
      </Modal>

      {/* Reject confirmation modal */}
      <Modal
        title={
          <Space>
            <ExclamationCircleOutlined style={{ color: '#EF4444' }} />
            Confirmer le refus
          </Space>
        }
        open={rejectModalOpen}
        onCancel={() => setRejectModalOpen(false)}
        onOk={handleRejectConfirm}
        confirmLoading={rejectLoading}
        okText="Refuser"
        okButtonProps={{ danger: true }}
        cancelText="Annuler"
      >
        {selectedExecution && (
          <div style={{ marginBottom: 16 }}>
            <p>
              Vous êtes sur le point de refuser l'exécution de{' '}
              <strong>{selectedExecution.action_name || `Action #${selectedExecution.action_id}`}</strong>{' '}
              en environnement <Tag color={getEnvironmentBadgeColor(selectedExecution.environment)}>{getEnvironmentLabel(selectedExecution.environment ?? '')}</Tag>
            </p>
            <p style={{ color: '#666', fontSize: 13 }}>
              Le demandeur sera notifié du refus.
            </p>
            <ApprovalContext parameters={selectedExecution.parameters} targets={selectedExecution.targets} />
          </div>
        )}
        <TextArea
          placeholder="Motif du refus (optionnel)"
          value={comment}
          onChange={(e) => setComment(e.target.value)}
          rows={3}
        />
      </Modal>
    </>
  );
}

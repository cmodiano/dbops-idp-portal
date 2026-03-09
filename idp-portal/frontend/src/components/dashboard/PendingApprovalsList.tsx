/**
 * PendingApprovalsList - List of executions pending DBA approval (Story 7.4).
 *
 * AC2: Display pending approvals with action, requester, environment, parameters, created_at.
 * AC6: Approve/Reject buttons with confirmation modal.
 */

import { useState } from 'react';
import { App, Table, Button, Space, Modal, Input, Tag, Typography, Tooltip, theme } from 'antd';
import type { TableProps } from 'antd';
import {
  CheckCircleOutlined,
  CloseCircleOutlined,
  ClockCircleOutlined,
  ExclamationCircleOutlined,
} from '@ant-design/icons';

import type { ExecutionResponse } from '../../types/api';
import { usePendingApprovals } from '../../hooks/usePendingApprovals';
import { getEnvironmentBadgeColor, getEnvironmentTagDarkStyle } from '../../utils/executionRenderers';
import { getEnvironmentLabel } from '../../utils/environmentHelpers';
import { STYLE_TOKENS } from '../../theme/styleTokens';
import { humanizeKey, formatParamValue, partitionParameters, ENV_CONFIG_LABELS, IMPACT_LEVEL_LABELS } from './approvalContextUtils';
import { useThemeMode } from '../../hooks/useThemeMode';

const { Text } = Typography;
const { TextArea } = Input;

// === ApprovalContext component (Story 58.6, AC4) ===

interface ApprovalContextProps {
  parameters: Record<string, unknown> | null;
  targets?: { target_type: string; target_id: string; target_name: string }[];
  compact?: boolean;
  /** When true (e.g. in PendingApprovalsList), approval is required by definition; don't show misleading "Non" from step config. */
  isPendingApproval?: boolean;
}

function ApprovalContext({ parameters, targets, compact, isPendingApproval }: ApprovalContextProps) {
  const { token } = theme.useToken();
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
    : { padding: 8, background: token.colorFillQuaternary, borderRadius: 4, fontSize: 12 };

  const formatEnvConfigValue = (key: string, value: unknown): string => {
    if (key === 'impact_level' && typeof value === 'string') {
      return IMPACT_LEVEL_LABELS[value] || humanizeKey(value);
    }
    return formatParamValue(value);
  };

  const envConfigEntries = hasEnvConfig ? Object.entries(envConfig!) : [];

  if (compact) {
    const parts: string[] = [];
    if (hasRichTargets) {
      parts.push(`Cibles: ${targets!.map(t => t.target_name || t.target_id).join(', ')}`);
    } else if (hasFallbackTargets) {
      parts.push(`Cibles: ${paramTargets.join(', ')}`);
    }
    if (hasStepParams) {
      const stepLines = Object.entries(stepParams!).map(([stepOrder, stepData]) => {
        const stepEntry = stepData && typeof stepData === 'object' ? stepData as { step_id?: string; step_name?: string; name?: string; parameters?: Record<string, unknown> } : null;
        const stepLabel = stepEntry?.step_name ?? stepEntry?.name ?? stepEntry?.step_id ?? `Étape ${stepOrder}`;
        const params = stepEntry?.parameters ?? null;
        const paramStr = params
          ? Object.entries(params).map(([pk, pv]) => `${humanizeKey(pk)}=${formatParamValue(pv)}`).join(', ')
          : '';
        return paramStr ? `${stepLabel}: ${paramStr}` : '';
      }).filter(Boolean);
      if (stepLines.length) parts.push(stepLines.join(' | '));
    }
    if (hasBusinessParams) {
      parts.push(Object.entries(businessParams).map(([k, v]) => `${humanizeKey(k)}=${formatParamValue(v)}`).join(', '));
    }
    if (envConfigEntries.length) {
      const impact = envConfig!.impact_level != null
        ? IMPACT_LEVEL_LABELS[String(envConfig!.impact_level)] || humanizeKey(String(envConfig!.impact_level))
        : null;
      if (impact) parts.push(`Impact: ${impact}`);
    }
    return (
      <div style={containerStyle}>
        <Text type="secondary">{parts.join(' · ')}</Text>
      </div>
    );
  }

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
            <div key={k} style={{ fontSize: 12, paddingLeft: 8 }}>
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
            const stepEntry = stepData && typeof stepData === 'object' ? stepData as { step_id?: string; step_name?: string; name?: string; parameters?: Record<string, unknown> } : null;
            const stepLabel = stepEntry?.step_name ?? stepEntry?.name ?? stepEntry?.step_id ?? `Étape ${stepOrder}`;
            const params = stepEntry?.parameters ?? null;
            return (
            <div key={stepOrder} style={{ fontSize: 12, paddingLeft: 8 }}>
              <Text type="secondary">{stepLabel} :</Text>
              {params && Object.entries(params).map(([pk, pv]) => (
                <div key={pk} style={{ paddingLeft: 16 }}>
                  {humanizeKey(pk)} : {formatParamValue(pv)}
                </div>
              ))}
            </div>
            );
          })}
        </div>
      )}

      {/* Env config - when isPendingApproval, show requires_approval as Oui (workflow has approval) */}
      {envConfigEntries.length > 0 && (
        <div>
          <Text strong style={{ fontSize: 12 }}>Configuration :</Text>
          {envConfigEntries.map(([k, v]) => (
            <div key={k} style={{ fontSize: 12, paddingLeft: 8 }}>
              <Text type="secondary">{ENV_CONFIG_LABELS[k] || humanizeKey(k)} :</Text>{' '}
              {isPendingApproval && k === 'requires_approval' ? 'Oui' : formatEnvConfigValue(k, v)}
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
  const { token } = theme.useToken();
  const { effectiveMode } = useThemeMode();
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
        <Tag
          color={getEnvironmentBadgeColor(env)}
          style={effectiveMode === 'dark' ? getEnvironmentTagDarkStyle(env) : undefined}
        >
          {getEnvironmentLabel(env ?? '')}
        </Tag>
      ),
    },
    {
      title: 'Contexte',
      key: 'context',
      render: (_: unknown, record: ExecutionResponse) => (
        <Space orientation="vertical" size={2} style={{ fontSize: 12 }}>
          <ApprovalContext parameters={record.parameters} targets={record.targets} compact isPendingApproval />
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
              en environnement{' '}
              <Tag
                color={getEnvironmentBadgeColor(selectedExecution.environment)}
                style={effectiveMode === 'dark' ? getEnvironmentTagDarkStyle(selectedExecution.environment) : undefined}
              >
                {getEnvironmentLabel(selectedExecution.environment ?? '')}
              </Tag>
            </p>
            <p style={{ color: token.colorTextSecondary, fontSize: 13 }}>
              L'exécution sera lancée immédiatement après approbation.
            </p>
            <ApprovalContext parameters={selectedExecution.parameters} targets={selectedExecution.targets} isPendingApproval />
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
              en environnement{' '}
              <Tag
                color={getEnvironmentBadgeColor(selectedExecution.environment)}
                style={effectiveMode === 'dark' ? getEnvironmentTagDarkStyle(selectedExecution.environment) : undefined}
              >
                {getEnvironmentLabel(selectedExecution.environment ?? '')}
              </Tag>
            </p>
            <p style={{ color: token.colorTextSecondary, fontSize: 13 }}>
              Le demandeur sera notifié du refus.
            </p>
            <ApprovalContext parameters={selectedExecution.parameters} targets={selectedExecution.targets} isPendingApproval />
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

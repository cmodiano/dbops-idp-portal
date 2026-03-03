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

const { Text } = Typography;
const { TextArea } = Input;

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
          {(env ?? '').toUpperCase()}
        </Tag>
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

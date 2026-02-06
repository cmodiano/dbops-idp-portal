/**
 * ValidationReportPanel — Detailed validation report drawer (Story 16.7, AC7).
 *
 * Displays grouped errors/warnings with navigation to problematic nodes
 * and summary statistics.
 */

import React from 'react';
import { Button, Drawer, Flex, Space, Statistic, Divider } from 'antd';
import {
  CloseCircleOutlined,
  WarningOutlined,
  AimOutlined,
  CheckCircleOutlined,
} from '@ant-design/icons';
import type { ValidationResult } from './WorkflowBuilderCanvas';

interface ValidationReportPanelProps {
  validation: ValidationResult | null;
  open: boolean;
  onClose: () => void;
  onGoToNode: (nodeId: string) => void;
}

interface ValidationErrorItem {
  nodeId: string;
  type: 'error' | 'warning';
  message: string;
}

const ErrorItem: React.FC<{ item: ValidationErrorItem; onGoToNode: (nodeId: string) => void }> = ({ item, onGoToNode }) => (
  <Flex justify="space-between" align="center" style={{ padding: '8px 0', borderBottom: '1px solid #f0f0f0' }}>
    <Flex gap={8} align="start">
      {item.type === 'error' ? (
        <CloseCircleOutlined style={{ color: '#ff4d4f', fontSize: 16, marginTop: 2 }} />
      ) : (
        <WarningOutlined style={{ color: '#fa8c16', fontSize: 16, marginTop: 2 }} />
      )}
      <div>
        <div style={{ fontWeight: 500 }}>{item.message}</div>
        {item.nodeId && (
          <div style={{ fontSize: 12, color: '#8c8c8c' }}>Nœud : {item.nodeId}</div>
        )}
      </div>
    </Flex>
    {item.nodeId && (
      <Button
        size="small"
        icon={<AimOutlined />}
        onClick={() => onGoToNode(item.nodeId)}
        aria-label={`Aller au nœud ${item.nodeId}`}
      >
        Aller au nœud
      </Button>
    )}
  </Flex>
);

const ValidationReportPanel: React.FC<ValidationReportPanelProps> = ({
  validation,
  open,
  onClose,
  onGoToNode,
}) => {
  if (!validation) return null;

  const errors = validation.errors.filter((e) => e.type === 'error');
  const warnings = validation.errors.filter((e) => e.type === 'warning');

  return (
    <Drawer
      title="Rapport de validation"
      open={open}
      onClose={onClose}
      size="default"
      aria-label="Rapport de validation du workflow"
      footer={
        <Flex justify="end">
          <Button onClick={onClose}>Fermer</Button>
        </Flex>
      }
    >
      <Flex vertical gap="middle" style={{ width: '100%' }}>
        {/* Summary stats */}
        <Space size="large">
          <Statistic
            title="Erreurs"
            value={errors.length}
            prefix={<CloseCircleOutlined style={{ color: '#ff4d4f' }} />}
            styles={{ content: { color: errors.length > 0 ? '#ff4d4f' : undefined } }}
          />
          <Statistic
            title="Avertissements"
            value={warnings.length}
            prefix={<WarningOutlined style={{ color: '#fa8c16' }} />}
            styles={{ content: { color: warnings.length > 0 ? '#fa8c16' : undefined } }}
          />
        </Space>

        {validation.valid && (
          <div style={{ textAlign: 'center', padding: '16px 0' }}>
            <CheckCircleOutlined style={{ fontSize: 48, color: '#52c41a' }} />
            <div style={{ marginTop: 8, fontWeight: 600, color: '#52c41a' }}>
              Workflow valide
            </div>
          </div>
        )}

        {errors.length > 0 && (
          <>
            <Divider titlePlacement="left" style={{ margin: '8px 0' }}>
              Erreurs bloquantes
            </Divider>
            {errors.map((error, idx) => (
              <ErrorItem key={`error-${idx}`} item={error} onGoToNode={onGoToNode} />
            ))}
          </>
        )}

        {warnings.length > 0 && (
          <>
            <Divider titlePlacement="left" style={{ margin: '8px 0' }}>
              Avertissements
            </Divider>
            {warnings.map((warning, idx) => (
              <ErrorItem key={`warning-${idx}`} item={warning} onGoToNode={onGoToNode} />
            ))}
          </>
        )}
      </Flex>
    </Drawer>
  );
};

export default ValidationReportPanel;

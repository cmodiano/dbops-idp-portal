/**
 * WorkflowBuilderToolbar — Story 26.5 AC4
 *
 * Extracted from WorkflowBuilderCanvas.tsx.
 * Toolbar with import, export dropdown, validate, and report buttons.
 */
import React from 'react';
import { Button, Dropdown, Space, Typography, theme } from 'antd';
import {
  CheckCircleOutlined,
  ExportOutlined,
  ImportOutlined,
} from '@ant-design/icons';
import type { ValidationResult } from '../../utils/workflowValidation';

const { Text } = Typography;

export interface WorkflowBuilderToolbarProps {
  disabled: boolean;
  exporting: boolean;
  validation: ValidationResult | null;
  exportMenuItems: Array<{ key: string; label: string; icon: React.ReactNode; onClick: () => void }>;
  onImportClick: () => void;
  onValidate: () => void;
  onShowReport: () => void;
  onClearValidation: () => void;
}

export const WorkflowBuilderToolbar: React.FC<WorkflowBuilderToolbarProps> = ({
  disabled,
  exporting,
  validation,
  exportMenuItems,
  onImportClick,
  onValidate,
  onShowReport,
  onClearValidation,
}) => {
  const { token } = theme.useToken();

  return (
    <div style={{ padding: '8px 12px', borderBottom: `1px solid ${token.colorBorderSecondary}`, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
      <Text type="secondary" style={{ fontSize: 12 }}>
        Glissez des actions depuis la palette. Connectez les ports pour créer des branches.
      </Text>
      <Space size="small">
        <Button
          size="small"
          icon={<ImportOutlined />}
          onClick={onImportClick}
          disabled={disabled}
          aria-label="Importer un workflow"
        >
          Importer
        </Button>
        <Dropdown
          menu={{ items: exportMenuItems }}
          trigger={['click']}
          disabled={disabled || exporting}
        >
          <Button
            size="small"
            icon={<ExportOutlined />}
            loading={exporting}
            aria-label="Exporter le workflow"
          >
            Exporter
          </Button>
        </Dropdown>
        <Button size="small" onClick={onValidate} icon={<CheckCircleOutlined />}>
          Valider le workflow
        </Button>
        {validation && (
          <>
            <Button size="small" onClick={onShowReport} type="default">
              Voir le rapport
            </Button>
            <Button size="small" onClick={onClearValidation} type="text">
              Effacer validation
            </Button>
          </>
        )}
      </Space>
    </div>
  );
};

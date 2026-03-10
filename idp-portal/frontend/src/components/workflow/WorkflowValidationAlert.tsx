/**
 * WorkflowValidationAlert — Story 26.5 AC5
 *
 * Extracted from WorkflowBuilderCanvas.tsx.
 * Shows success/error alert after workflow validation.
 */
import type { FC } from 'react';
import { Alert } from 'antd';
import { WarningOutlined } from '@ant-design/icons';
import type { ValidationResult } from '../../utils/workflowValidation';

export interface WorkflowValidationAlertProps {
  validation: ValidationResult | null;
}

export const WorkflowValidationAlert: FC<WorkflowValidationAlertProps> = ({ validation }) => {
  if (!validation) return null;

  return (
    <div style={{ padding: '4px 12px' }}>
      {validation.valid ? (
        <Alert type="success" title="Workflow valide" showIcon banner />
      ) : (
        <Alert
          type="error"
          title={`${validation.errors.filter((e) => e.type === 'error').length} erreur(s), ${validation.errors.filter((e) => e.type === 'warning').length} avertissement(s)`}
          showIcon
          banner
          icon={<WarningOutlined />}
        />
      )}
    </div>
  );
};

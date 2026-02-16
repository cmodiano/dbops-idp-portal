/**
 * WorkflowValidationAlert — Story 26.5 AC5
 *
 * Extracted from WorkflowBuilderCanvas.tsx.
 * Shows success/error alert after workflow validation.
 */
import React from 'react';
import { Alert } from 'antd';
import { WarningOutlined } from '@ant-design/icons';
import type { ValidationResult } from '../../utils/workflowValidation';

export interface WorkflowValidationAlertProps {
  validation: ValidationResult | null;
}

export const WorkflowValidationAlert: React.FC<WorkflowValidationAlertProps> = ({ validation }) => {
  if (!validation) return null;

  return (
    <div style={{ padding: '4px 12px' }}>
      {validation.valid ? (
        <Alert type="success" message="Workflow valide" showIcon banner />
      ) : (
        <Alert
          type="error"
          message={`${validation.errors.filter((e) => e.type === 'error').length} erreur(s), ${validation.errors.filter((e) => e.type === 'warning').length} avertissement(s)`}
          showIcon
          banner
          icon={<WarningOutlined />}
        />
      )}
    </div>
  );
};

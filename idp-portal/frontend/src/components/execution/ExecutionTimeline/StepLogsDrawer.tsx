/**
 * StepLogsDrawer — Story 34.12 (SOLID-FE-1)
 *
 * Extracted from ExecutionTimeline.tsx.
 * Ant Design Drawer with detailed step logs (timestamps, error, JSON output).
 */

import { Drawer } from 'antd';
import type { ExecutionStepResponse } from '../../../types/api';

interface StepLogsDrawerProps {
  step: ExecutionStepResponse | null;
  open: boolean;
  onClose: () => void;
  contentRef: React.RefObject<HTMLDivElement>;
}

export function StepLogsDrawer({ step, open, onClose, contentRef }: StepLogsDrawerProps) {
  return (
    <Drawer
      title={step ? `Logs détaillés - ${step.step_name}` : 'Logs détaillés'}
      open={open}
      onClose={onClose}
      styles={{ wrapper: { width: 480 } }}
      destroyOnHidden
      aria-label="Logs détaillés de l'étape"
    >
      {step && (
        <div ref={contentRef} tabIndex={-1} style={{ fontFamily: 'monospace', fontSize: 12 }}>
          {step.started_at && (
            <p style={{ marginBottom: 8 }}>
              <strong>Début :</strong> {new Date(step.started_at).toLocaleString()}
            </p>
          )}
          {step.completed_at && (
            <p style={{ marginBottom: 12 }}>
              <strong>Fin :</strong> {new Date(step.completed_at).toLocaleString()}
            </p>
          )}
          {step.error_message && (
            <div style={{ color: '#EF4444', marginBottom: 12 }}>
              <strong>Erreur :</strong>
              <pre style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word', margin: '4px 0 0 0' }}>
                {step.error_message}
              </pre>
            </div>
          )}
          {step.output != null && typeof step.output === 'object' && (
            <div>
              <strong>Output :</strong>
              <pre
                style={{
                  margin: '4px 0 0 0',
                  padding: 12,
                  backgroundColor: 'rgba(0,0,0,0.04)',
                  borderRadius: 4,
                  overflow: 'auto',
                  maxHeight: 400,
                  whiteSpace: 'pre-wrap',
                  wordBreak: 'break-word',
                }}
              >
                {JSON.stringify(step.output, null, 2)}
              </pre>
            </div>
          )}
        </div>
      )}
    </Drawer>
  );
}

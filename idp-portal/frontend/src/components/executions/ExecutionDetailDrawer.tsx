/**
 * ExecutionDetailDrawer - Drawer with ExecutionTimeline or WorkflowExecutionGraph
 *
 * Story 26.4 - AC5: Extracted from ExecutionsPage.tsx.
 * Shows execution detail with conditional rendering based on item_type.
 */
import { Drawer, Skeleton, Alert, Button } from 'antd';
import { ExecutionTimeline } from '../execution/ExecutionTimeline';
import { WorkflowExecutionGraph } from '../execution/WorkflowExecutionGraph';
import { ErrorBoundary } from '../ErrorBoundary';
import type { ExecutionResponse, ExecutionStepResponse } from '../../types/api';
import type { CatalogActionDetail } from '../../services/catalog_service';

export interface ExecutionDetailDrawerProps {
  open: boolean;
  execution: ExecutionResponse | null;
  steps: ExecutionStepResponse[];
  actionDetail: CatalogActionDetail | null;
  loading: boolean;
  error: string | null;
  onClose: () => void;
  onExecutionUpdate: (updated: ExecutionResponse) => void;
}

export const ExecutionDetailDrawer: React.FC<ExecutionDetailDrawerProps> = ({
  open,
  execution,
  steps,
  actionDetail,
  loading,
  error,
  onClose,
  onExecutionUpdate,
}) => (
  <Drawer
    title={execution ? `Exécution — ${execution.action_name || `Action #${execution.action_id}`}` : 'Détail exécution'}
    open={open}
    onClose={onClose}
    width={execution?.item_type === 'workflow' && actionDetail?.workflow_steps ? '90%' : undefined}
    size={execution?.item_type === 'workflow' && actionDetail?.workflow_steps ? undefined : 'default'}
    styles={
      execution?.item_type === 'workflow' && actionDetail?.workflow_steps
        ? { body: { padding: 0, height: '100%', display: 'flex', flexDirection: 'column' } }
        : { body: { width: 480 } }
    }
    destroyOnClose
  >
    {loading ? (
      <Skeleton active paragraph={{ rows: 6 }} />
    ) : error ? (
      <Alert type="error" message="Erreur de chargement" description={error} showIcon />
    ) : execution ? (
      execution.item_type === 'workflow' &&
      actionDetail?.workflow_steps &&
      actionDetail.workflow_steps.length > 0 ? (
        <ErrorBoundary
          fallback={(err, resetError) => (
            <div style={{ padding: 16 }}>
              <Alert type="error" showIcon message="Erreur d'affichage du workflow" description={err.message} />
              <Button onClick={resetError} style={{ marginTop: 8 }}>Réessayer</Button>
            </div>
          )}
        >
          <div style={{ flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column' }}>
            <WorkflowExecutionGraph
              executionId={execution.id}
              workflowSteps={actionDetail.workflow_steps}
              execution={execution}
              onExecutionUpdate={onExecutionUpdate}
            />
          </div>
        </ErrorBoundary>
      ) : (
        <ErrorBoundary
          fallback={(err, resetError) => (
            <div style={{ padding: 16 }}>
              <Alert type="error" showIcon message="Erreur d'affichage de la timeline" description={err.message} />
              <Button onClick={resetError} style={{ marginTop: 8 }}>Réessayer</Button>
            </div>
          )}
        >
          <ExecutionTimeline
            execution={execution}
            steps={steps}
            mode="historical"
          />
        </ErrorBoundary>
      )
    ) : null}
  </Drawer>
);

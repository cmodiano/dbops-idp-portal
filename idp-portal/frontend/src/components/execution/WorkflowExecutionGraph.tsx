/**
 * WorkflowExecutionGraph — Read-only workflow execution visualization (Story 19.2).
 *
 * Reuses WorkflowBuilderCanvas components (React Flow) in read-only mode to display
 * the workflow graph with real-time status indicators for each step.
 *
 * Features:
 * - Visual graph with Start → Steps → End nodes (AC2)
 * - Read-only: zoom/pan enabled, drag/edit disabled (AC6)
 * - Real-time status updates via polling/WebSocket (AC5)
 * - Active step highlighting with pulse animation (AC3)
 * - Completed/failed/pending/skipped indicators (AC4)
 * - Path traversal visual distinction (AC8)
 * - Success/error branch differentiation (AC9)
 * - Legend and tooltips (AC10)
 */

import { useState, useMemo, useEffect, useCallback, useRef } from 'react';
import { getExecutionSteps } from '../../services/execution_service';
import logger from '../../services/logger';
import {
  ReactFlow,
  Controls,
  Background,
  MiniMap,
  useNodesState,
  useEdgesState,
  type Node,
  type Edge,
  type ReactFlowInstance,
  ReactFlowProvider,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { Card, Space, Typography, Spin, Alert, Badge } from 'antd';
import type { WorkflowStep, ExecutionResponse, ExecutionStepResponse, ExecutionStepStatus } from '../../types/api';
import { useExecutionPolling } from '../../hooks/useExecutionPolling';
import { useWebSocket } from '../../hooks/useWebSocket';
import {
  workflowStepsToReactFlow,
  START_NODE_ID,
  END_NODE_ID,
} from '../../utils/workflowConversion';
import WorkflowStepNode from '../admin/WorkflowStepNode';
import StartNode from '../admin/StartNode';
import EndNode from '../admin/EndNode';
import CustomEdge from '../admin/CustomEdge';
import { StepDetailDrawer } from './StepDetailDrawer';

const { Text } = Typography;

// Couleurs graphe React Flow — config locale justifiée (Story 35.1 AC4 Option B, SOLID-FE-10).
// Les couleurs hex servent la lisibilité visuelle du graphe React Flow, pas les badges Ant Design.
// RUNNING = orange (#fa8c16) pour étape active très visible (vs bleu #3B82F6 dans STEP_STATUS_COLOR).
// SELECTED = gold (#faad14) — sélection nœud AC7, aucun équivalent dans execution-status.ts.
// Ne pas migrer vers STEP_STATUS_COLOR : usage graphe (hex) différent du usage badge (BadgeStatusType).
const STATUS_COLORS = {
  RUNNING: '#fa8c16', // Orange — étape active, bien visible (différent de STEP_STATUS_COLOR '#3B82F6')
  COMPLETED: '#52c41a',
  FAILED: '#ff4d4f',
  PENDING: '#8c8c8c',
  SKIPPED: '#8c8c8c',
  SELECTED: '#faad14', // Story 19.3 AC7: Golden border for selected node — pas d'équivalent dans execution-status.ts
} as const;

interface WorkflowExecutionGraphProps {
  executionId: number;
  workflowSteps: WorkflowStep[];
  execution: ExecutionResponse | null;
  /** Callback when execution data is updated via polling/WebSocket (for parent header sync). */
  onExecutionUpdate?: (execution: ExecutionResponse) => void;
}

const nodeTypes = {
  workflowStep: WorkflowStepNode,
  start: StartNode,
  end: EndNode,
};

const edgeTypes = {
  customEdge: CustomEdge,
};

/** Calculate human-readable duration between two timestamps. */
function calculateStepDuration(step: ExecutionStepResponse): string | null {
  if (!step.started_at || !step.completed_at) return null;
  const start = new Date(step.started_at).getTime();
  const end = new Date(step.completed_at).getTime();
  const durationSec = Math.floor((end - start) / 1000);
  if (durationSec < 60) return `${durationSec}s`;
  const minutes = Math.floor(durationSec / 60);
  const seconds = durationSec % 60;
  return seconds ? `${minutes}m ${seconds}s` : `${minutes}m`;
}

/** Get subtle border style for the React Flow wrapper (AC3, AC4). */
function getNodeStyle(status: ExecutionStepStatus | undefined): React.CSSProperties {
  // The actual visible border is handled by WorkflowStepNode's inner div.
  // These wrapper styles provide minimal reinforcement.
  switch (status) {
    case 'RUNNING':
      return { opacity: 1 };
    case 'COMPLETED':
      return { opacity: 1 };
    case 'FAILED':
      return { opacity: 1 };
    case 'SKIPPED':
      return { opacity: 0.6 };
    default: // PENDING
      return { opacity: 0.7 };
  }
}

function WorkflowExecutionGraphInner({
  executionId,
  workflowSteps,
  execution,
  onExecutionUpdate,
}: WorkflowExecutionGraphProps) {
  // Story 19.3 AC1: Selected step state for drawer
  const [selectedStepId, setSelectedStepId] = useState<string | null>(null);

  // Store React Flow instance ref for delayed fitView
  const rfInstanceRef = useRef<ReactFlowInstance | null>(null);

  // onInit: React Flow is ready — store instance and do a delayed fitView
  const handleInit = useCallback((instance: ReactFlowInstance) => {
    rfInstanceRef.current = instance;
    // Delay fitView to let the drawer animation complete (antd ~300ms + buffer)
    setTimeout(() => {
      instance.fitView({ padding: 0.3, duration: 300 });
    }, 500);
  }, []);

  // Story 19.3 AC1, AC8: Handle node click — open drawer for action nodes, ignore Start/End
  const handleNodeClick = useCallback((_event: React.MouseEvent, node: Node) => {
    if (node.id === START_NODE_ID || node.id === END_NODE_ID) {
      return;
    }
    setSelectedStepId(node.id);
  }, []);

  // AC5: Real-time updates via WebSocket + polling fallback
  // Skip real-time for terminal executions (no need to poll/WS for completed/failed/cancelled)
  const TERMINAL_STATUSES = ['COMPLETED', 'FAILED', 'CANCELLED', 'REJECTED'];
  const isTerminal = execution ? TERMINAL_STATUSES.includes(execution.status) : false;

  // One-time fetch for terminal executions (load steps without WS/polling)
  const [staticSteps, setStaticSteps] = useState<ExecutionStepResponse[]>([]);
  const [stepsError, setStepsError] = useState<string | null>(null);
  useEffect(() => {
    if (isTerminal && executionId) {
      setStepsError(null);
      getExecutionSteps(executionId)
        .then((steps) => {
          setStaticSteps(steps);
          setStepsError(null);
        })
        .catch((err: unknown) => {
          const message = err instanceof Error ? err.message : 'Erreur inconnue';
          logger.error('Failed to load execution steps', {
            executionId,
            error: message,
          });
          setStepsError(message);
        });
    }
  }, [isTerminal, executionId]);

  // Skip WebSocket entirely in simulation mode (no WS server in Docker/dev)
  const forcePolling = import.meta.env.VITE_SIMULATE_EXECUTION === 'true';
  const wsExecutionId = isTerminal || forcePolling ? null : executionId;
  const ws = useWebSocket(wsExecutionId);
  const polling = useExecutionPolling({
    executionId: isTerminal ? null : executionId,
    enabled: !isTerminal && (forcePolling || ws.error != null),
  });

  // Merge steps: terminal → static fetch, polling → polling, WS → WS
  const executionSteps: ExecutionStepResponse[] = isTerminal
    ? staticSteps
    : forcePolling
      ? polling.steps
      : (ws.error == null ? ws.steps : polling.steps);
  // Live execution from real-time only (NOT from prop — that would cause infinite loop)
  const liveExecutionFromRealtime = !isTerminal
    ? (forcePolling ? polling.execution : (ws.error == null ? ws.execution : polling.execution))
    : null;
  const isLoading = isTerminal ? false : (ws.error == null ? ws.loading : false);

  // Use ref for callback to avoid infinite re-render loop
  const onExecutionUpdateRef = useRef(onExecutionUpdate);
  onExecutionUpdateRef.current = onExecutionUpdate;

  // Propagate execution updates to parent (for header status sync)
  // Only from real-time sources (WS/polling), never from the prop itself
  useEffect(() => {
    if (liveExecutionFromRealtime && onExecutionUpdateRef.current) {
      onExecutionUpdateRef.current(liveExecutionFromRealtime);
    }
  }, [liveExecutionFromRealtime]);

  // AC2: Convert workflow steps → React Flow nodes + edges
  const { nodes: baseNodes, edges: baseEdges } = useMemo(() => {
    if (!workflowSteps || workflowSteps.length === 0) {
      return { nodes: [] as Node[], edges: [] as Edge[] };
    }
    return workflowStepsToReactFlow(workflowSteps);
  }, [workflowSteps]);

  const [nodes, setNodes, onNodesChange] = useNodesState(baseNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(baseEdges);

  // AC3, AC4: Enrich nodes with execution step status
  useEffect(() => {
    if (baseNodes.length === 0) return;

    // Map execution steps by step_order to find corresponding workflow step
    const stepStatusMap = new Map<string, ExecutionStepResponse>();
    executionSteps.forEach((execStep) => {
      // Match by step_order (1-based) to workflowSteps index (0-based)
      const wfStep = workflowSteps[execStep.step_order - 1];
      if (wfStep?.step_id) {
        stepStatusMap.set(wfStep.step_id, execStep);
      }
    });

    const enrichedNodes = baseNodes.map((node) => {
      if (node.id === START_NODE_ID || node.id === END_NODE_ID) {
        return node;
      }

      const execStep = stepStatusMap.get(node.id);
      const status = execStep?.status;
      const duration = execStep ? calculateStepDuration(execStep) : null;
      // Story 19.3 AC7: Selected node indicator
      const isSelected = node.id === selectedStepId;

      return {
        ...node,
        data: {
          ...node.data,
          // Story 19.2: Execution status data for tooltip enrichment (Task 3)
          executionStatus: status ?? 'PENDING',
          executionDuration: duration,
        },
        style: {
          ...node.style,
          ...getNodeStyle(status),
          // Story 19.3 AC7: Golden border for selected node (overrides status border)
          ...(isSelected && {
            borderColor: STATUS_COLORS.SELECTED,
            borderWidth: 4,
            boxShadow: `0 0 12px ${STATUS_COLORS.SELECTED}80`,
            opacity: 1,
          }),
          transition: 'border-color 0.3s, opacity 0.3s, box-shadow 0.3s',
        },
        className: status === 'RUNNING' && !isSelected ? 'workflow-node-running' : undefined,
      };
    });

    setNodes(enrichedNodes);
  }, [baseNodes, executionSteps, workflowSteps, selectedStepId, setNodes]);

  // AC8: Enrich edges for traversed path
  useEffect(() => {
    if (baseEdges.length === 0) return;

    const stepStatusMap = new Map<string, ExecutionStepResponse>();
    executionSteps.forEach((execStep) => {
      const wfStep = workflowSteps[execStep.step_order - 1];
      if (wfStep?.step_id) {
        stepStatusMap.set(wfStep.step_id, execStep);
      }
    });

    const enrichedEdges = baseEdges.map((edge) => {
      const sourceStep = stepStatusMap.get(edge.source);

      if (sourceStep && (sourceStep.status === 'COMPLETED' || sourceStep.status === 'FAILED')) {
        // AC8: Traversed path — thicker, fully opaque
        return {
          ...edge,
          style: {
            ...edge.style,
            strokeWidth: 3,
            opacity: 1,
          },
          animated: false,
        };
      }

      if (sourceStep?.status === 'RUNNING') {
        // Edge from running step — animated
        return {
          ...edge,
          style: {
            ...edge.style,
            strokeWidth: 2,
            opacity: 1,
          },
          animated: true,
        };
      }

      // AC8: Untraversed path — dashed, semi-transparent
      return {
        ...edge,
        style: {
          ...edge.style,
          strokeWidth: 1,
          opacity: 0.3,
          strokeDasharray: '5,5',
        },
        animated: false,
      };
    });

    setEdges(enrichedEdges);
  }, [baseEdges, executionSteps, workflowSteps, setEdges]);

  if (isLoading && executionSteps.length === 0) {
    return (
      <div style={{ textAlign: 'center', padding: '48px 0' }}>
        <Spin size="large" />
      </div>
    );
  }

  if (!workflowSteps || workflowSteps.length === 0) {
    return (
      <Alert
        type="warning"
        showIcon
        title="Workflow vide"
        description="Aucune étape définie dans ce workflow."
      />
    );
  }

  return (
    <div data-testid="workflow-execution-graph" style={{ height: 'calc(100vh - 160px)', minHeight: 500, position: 'relative' }}>
      {stepsError && (
        <Alert
          type="error"
          showIcon
          closable
          title="Erreur de chargement des étapes"
          description={stepsError}
          style={{ marginBottom: 8 }}
          onClose={() => setStepsError(null)}
        />
      )}
      {/* AC10: Legend */}
      <Card
        size="small"
        style={{
          position: 'absolute',
          top: 8,
          right: 8,
          zIndex: 10,
          maxWidth: 220,
        }}
      >
        <Text strong style={{ display: 'block', marginBottom: 8, fontSize: 13 }}>
          Légende
        </Text>
        <Space orientation="vertical" size={4}>
          <Space size={8}>
            <Badge color={STATUS_COLORS.RUNNING} />
            <Text type="secondary">En cours</Text>
          </Space>
          <Space size={8}>
            <Badge color={STATUS_COLORS.COMPLETED} />
            <Text type="secondary">Terminé (succès)</Text>
          </Space>
          <Space size={8}>
            <Badge color={STATUS_COLORS.FAILED} />
            <Text type="secondary">Échoué</Text>
          </Space>
          <Space size={8}>
            <Badge color={STATUS_COLORS.PENDING} />
            <Text type="secondary">À venir / Annulé</Text>
          </Space>
        </Space>
      </Card>

      {/* AC2: React Flow graph */}
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onNodeClick={handleNodeClick}
        onInit={handleInit}
        nodeTypes={nodeTypes}
        edgeTypes={edgeTypes}
        fitView
        fitViewOptions={{ padding: 0.3 }}
        // AC6: Read-only mode
        nodesDraggable={false}
        nodesConnectable={false}
        elementsSelectable={true}
        panOnDrag={true}
        zoomOnScroll={true}
        zoomOnPinch={true}
        zoomOnDoubleClick={false}
        deleteKeyCode={null}
        minZoom={0.3}
        maxZoom={3}
      >
        <Background />
        <Controls showInteractive={false} />
        <MiniMap nodeStrokeWidth={3} zoomable pannable />
      </ReactFlow>

      {/* Story 19.3 AC1: Step detail drawer */}
      <StepDetailDrawer
        open={selectedStepId != null}
        stepId={selectedStepId}
        executionId={executionId}
        executionSteps={executionSteps}
        workflowSteps={workflowSteps}
        onClose={() => setSelectedStepId(null)}
      />

      {/* AC3: Subtle pulse animation for active (RUNNING) step */}
      <style>{`
        @keyframes workflow-node-pulse {
          0%, 100% {
            box-shadow: 0 0 4px ${STATUS_COLORS.RUNNING}30;
          }
          50% {
            box-shadow: 0 0 10px ${STATUS_COLORS.RUNNING}50;
          }
        }
        .workflow-node-running > div {
          animation: workflow-node-pulse 1.5s ease-in-out infinite;
        }
      `}</style>
    </div>
  );
}

export function WorkflowExecutionGraph(props: WorkflowExecutionGraphProps) {
  // Memoize the onExecutionUpdate to prevent re-renders
  return (
    <ReactFlowProvider>
      <WorkflowExecutionGraphInner {...props} />
    </ReactFlowProvider>
  );
}

export type { WorkflowExecutionGraphProps };

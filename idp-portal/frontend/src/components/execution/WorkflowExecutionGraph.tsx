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

import { useState, useMemo, useEffect, useCallback } from 'react';
import {
  ReactFlow,
  Controls,
  Background,
  MiniMap,
  useNodesState,
  useEdgesState,
  type Node,
  type Edge,
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
} from '../admin/WorkflowBuilderCanvas';
import WorkflowStepNode from '../admin/WorkflowStepNode';
import StartNode from '../admin/StartNode';
import EndNode from '../admin/EndNode';
import CustomEdge from '../admin/CustomEdge';
import { StepDetailDrawer } from './StepDetailDrawer';
import logger from '../../services/logger';

const { Text } = Typography;

// Status colors
const STATUS_COLORS = {
  RUNNING: '#1677ff',
  COMPLETED: '#52c41a',
  FAILED: '#ff4d4f',
  PENDING: '#8c8c8c',
  SKIPPED: '#8c8c8c',
  SELECTED: '#faad14', // Story 19.3 AC7: Golden border for selected node
} as const;

interface WorkflowExecutionGraphProps {
  executionId: number;
  workflowSteps: WorkflowStep[];
  execution: ExecutionResponse | null;
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

/** Get border style for a node based on execution status (AC3, AC4). */
function getNodeStyle(status: ExecutionStepStatus | undefined): React.CSSProperties {
  switch (status) {
    case 'RUNNING':
      return {
        borderColor: STATUS_COLORS.RUNNING,
        borderWidth: 3,
        boxShadow: `0 0 8px ${STATUS_COLORS.RUNNING}40`,
      };
    case 'COMPLETED':
      return {
        borderColor: STATUS_COLORS.COMPLETED,
        borderWidth: 2,
      };
    case 'FAILED':
      return {
        borderColor: STATUS_COLORS.FAILED,
        borderWidth: 2,
      };
    case 'SKIPPED':
      return {
        borderColor: STATUS_COLORS.PENDING,
        borderWidth: 1,
        opacity: 0.6,
      };
    default: // PENDING
      return {
        borderColor: '#d9d9d9',
        borderWidth: 1,
        opacity: 0.7,
      };
  }
}

function WorkflowExecutionGraphInner({
  executionId,
  workflowSteps,
  execution,
}: WorkflowExecutionGraphProps) {
  // Story 19.3 AC1: Selected step state for drawer
  const [selectedStepId, setSelectedStepId] = useState<string | null>(null);

  // Story 19.3 AC1, AC8: Handle node click — open drawer for action nodes, ignore Start/End
  const handleNodeClick = useCallback((_event: React.MouseEvent, node: Node) => {
    if (node.id === START_NODE_ID || node.id === END_NODE_ID) {
      return;
    }
    setSelectedStepId(node.id);
  }, []);

  // AC5: Real-time updates via WebSocket + polling fallback
  const ws = useWebSocket(executionId);
  const polling = useExecutionPolling({
    executionId,
    enabled: ws.error != null || import.meta.env.VITE_SIMULATE_EXECUTION === 'true',
  });

  // Merge steps from WebSocket or polling
  const executionSteps: ExecutionStepResponse[] = ws.error == null ? ws.steps : polling.steps;
  const isLoading = ws.error == null ? ws.loading : false;

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
    <div data-testid="workflow-execution-graph" style={{ height: 500, position: 'relative' }}>
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
        <Space direction="vertical" size={4}>
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
        nodeTypes={nodeTypes}
        edgeTypes={edgeTypes}
        fitView
        fitViewOptions={{ padding: 0.2 }}
        // AC6: Read-only mode
        nodesDraggable={false}
        nodesConnectable={false}
        elementsSelectable={true}
        panOnDrag={true}
        zoomOnScroll={true}
        zoomOnPinch={true}
        zoomOnDoubleClick={false}
        deleteKeyCode={null}
        minZoom={0.5}
        maxZoom={2}
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

      {/* AC3: Pulse animation CSS */}
      <style>{`
        @keyframes workflow-node-pulse {
          0%, 100% { box-shadow: 0 0 4px ${STATUS_COLORS.RUNNING}40; }
          50% { box-shadow: 0 0 12px ${STATUS_COLORS.RUNNING}80; }
        }
        .workflow-node-running > div {
          animation: workflow-node-pulse 2s ease-in-out infinite;
        }
      `}</style>
    </div>
  );
}

export function WorkflowExecutionGraph(props: WorkflowExecutionGraphProps) {
  return (
    <ReactFlowProvider>
      <WorkflowExecutionGraphInner {...props} />
    </ReactFlowProvider>
  );
}

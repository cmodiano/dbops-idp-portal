/**
 * WorkflowBuilderCanvas — Visual workflow builder using React Flow (Story 16.5).
 *
 * Features:
 * - Zoomable/pannable canvas (AC1)
 * - Drag-and-drop actions from palette (AC2)
 * - Success/error connections between nodes (AC3, AC4)
 * - Step configuration panel (AC5)
 * - Node and edge deletion (AC6, AC7)
 * - Workflow validation with visual feedback (AC8)
 * - Bidirectional sync with WorkflowStep[] (Task 7)
 */

import React, { useCallback, useMemo, useState, useRef, useEffect } from 'react';
import {
  ReactFlow,
  Controls,
  Background,
  MiniMap,
  addEdge,
  useNodesState,
  useEdgesState,
  type Connection,
  type Edge,
  type Node,
  ReactFlowProvider,
  useReactFlow,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { Alert, Button, Space, theme, Typography } from 'antd';
import { CheckCircleOutlined, WarningOutlined } from '@ant-design/icons';
import type { WorkflowStep, ActionListItem } from '../../types/api';
import WorkflowStepNode, { type WorkflowStepNodeData } from './WorkflowStepNode';
import { ActionPalette } from './ActionPalette';
import { StepConfigPanel } from './StepConfigPanel';

const { Text } = Typography;

// ── Data conversion utilities ──────────────────────────────────────────────

function generateStepId(): string {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID();
  }
  return `step-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

/** Convert WorkflowStep[] → React Flow nodes + edges */
export function workflowStepsToReactFlow(
  steps: WorkflowStep[],
): { nodes: Node[]; edges: Edge[] } {
  const nodes: Node[] = steps.map((step, index) => ({
    id: step.step_id ?? `step-${index}`,
    type: 'workflowStep',
    position: { x: (index % 4) * 280, y: Math.floor(index / 4) * 200 },
    data: {
      action_id: step.referenced_action_id,
      action_name: step.name ?? `Action #${step.referenced_action_id}`,
      action_engine: '',
      action_platform: '',
      name: step.name,
      retry_enabled: step.retry_enabled ?? false,
      retry_max_attempts: step.retry_max_attempts ?? null,
      retry_interval_seconds: step.retry_interval_seconds ?? null,
      retry_backoff_multiplier: step.retry_backoff_multiplier ?? null,
    } satisfies WorkflowStepNodeData,
  }));

  const edges: Edge[] = [];
  steps.forEach((step) => {
    const sourceId = step.step_id;
    if (!sourceId) return;

    if (step.on_success_step_id) {
      edges.push({
        id: `${sourceId}_success_${step.on_success_step_id}`,
        source: sourceId,
        target: step.on_success_step_id,
        sourceHandle: 'success',
        targetHandle: 'input',
        type: 'smoothstep',
        animated: false,
        style: { stroke: '#52c41a', strokeWidth: 2 },
        label: 'succès',
        labelStyle: { fontSize: 10, fill: '#52c41a' },
      });
    }
    if (step.on_error_step_id) {
      edges.push({
        id: `${sourceId}_error_${step.on_error_step_id}`,
        source: sourceId,
        target: step.on_error_step_id,
        sourceHandle: 'error',
        targetHandle: 'input',
        type: 'smoothstep',
        animated: false,
        style: { stroke: '#ff4d4f', strokeWidth: 2 },
        label: 'erreur',
        labelStyle: { fontSize: 10, fill: '#ff4d4f' },
      });
    }
  });

  return { nodes, edges };
}

/** Convert React Flow nodes + edges → WorkflowStep[] */
export function reactFlowToWorkflowSteps(
  nodes: Node[],
  edges: Edge[],
): WorkflowStep[] {
  return nodes.map((node, index) => {
    const data = node.data as unknown as WorkflowStepNodeData;
    const successEdge = edges.find(
      (e) => e.source === node.id && e.sourceHandle === 'success'
    );
    const errorEdge = edges.find(
      (e) => e.source === node.id && e.sourceHandle === 'error'
    );

    return {
      order: index + 1,
      step_id: node.id,
      name: data.name,
      referenced_action_id: data.action_id,
      on_success_step_id: successEdge?.target ?? null,
      on_error_step_id: errorEdge?.target ?? null,
      retry_enabled: data.retry_enabled ?? false,
      retry_max_attempts: data.retry_max_attempts ?? null,
      retry_interval_seconds: data.retry_interval_seconds ?? null,
      retry_backoff_multiplier: data.retry_backoff_multiplier ?? null,
    };
  });
}

// ── Validation ─────────────────────────────────────────────────────────────

export interface ValidationError {
  nodeId: string;
  type: 'error' | 'warning';
  message: string;
}

export interface ValidationResult {
  valid: boolean;
  errors: ValidationError[];
}

export function validateWorkflowGraph(nodes: Node[], edges: Edge[]): ValidationResult {
  const errors: ValidationError[] = [];

  if (nodes.length === 0) {
    return { valid: false, errors: [{ nodeId: '', type: 'error', message: 'Au moins une étape est requise' }] };
  }

  // 1. Check every node has at least one output connection
  nodes.forEach((node) => {
    const hasSuccessEdge = edges.some((e) => e.source === node.id && e.sourceHandle === 'success');
    const hasErrorEdge = edges.some((e) => e.source === node.id && e.sourceHandle === 'error');

    if (!hasSuccessEdge && !hasErrorEdge) {
      errors.push({
        nodeId: node.id,
        type: 'warning',
        message: `Pas de chemin de sortie`,
      });
    }
  });

  // 2. Detect orphan nodes (not reachable from start)
  if (nodes.length > 1) {
    const reachableNodes = new Set<string>();
    const startNode = nodes[0];
    const queue = [startNode.id];

    while (queue.length > 0) {
      const current = queue.shift()!;
      if (reachableNodes.has(current)) continue;
      reachableNodes.add(current);

      edges
        .filter((e) => e.source === current)
        .forEach((e) => {
          if (!reachableNodes.has(e.target)) {
            queue.push(e.target);
          }
        });
    }

    nodes.forEach((node) => {
      if (!reachableNodes.has(node.id)) {
        errors.push({
          nodeId: node.id,
          type: 'error',
          message: `Non atteignable depuis le début`,
        });
      }
    });
  }

  // 3. Detect infinite loops (DFS cycle detection)
  const visited = new Set<string>();
  const inStack = new Set<string>();
  const loopNodes = new Set<string>();

  function dfs(nodeId: string): boolean {
    if (inStack.has(nodeId)) {
      loopNodes.add(nodeId);
      return true;
    }
    if (visited.has(nodeId)) return false;

    visited.add(nodeId);
    inStack.add(nodeId);

    const outEdges = edges.filter((e) => e.source === nodeId);
    for (const edge of outEdges) {
      if (dfs(edge.target)) {
        loopNodes.add(nodeId);
      }
    }

    inStack.delete(nodeId);
    return false;
  }

  nodes.forEach((node) => {
    if (!visited.has(node.id)) {
      dfs(node.id);
    }
  });

  loopNodes.forEach((nodeId) => {
    errors.push({
      nodeId,
      type: 'error',
      message: `Boucle infinie détectée`,
    });
  });

  return {
    valid: errors.filter((e) => e.type === 'error').length === 0,
    errors,
  };
}

// ── Node types registration ────────────────────────────────────────────────

const nodeTypes = {
  workflowStep: WorkflowStepNode,
};

// ── Main component ─────────────────────────────────────────────────────────

export interface WorkflowBuilderCanvasProps {
  steps: WorkflowStep[];
  onChange: (steps: WorkflowStep[]) => void;
  disabled?: boolean;
}

function WorkflowBuilderCanvasInner({
  steps,
  onChange,
  disabled = false,
}: WorkflowBuilderCanvasProps) {
  const { token } = theme.useToken();
  const reactFlowWrapper = useRef<HTMLDivElement>(null);
  const { screenToFlowPosition } = useReactFlow();

  // Convert initial steps to React Flow format
  const initial = useMemo(() => workflowStepsToReactFlow(steps), []);
  const [nodes, setNodes, onNodesChange] = useNodesState(initial.nodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initial.edges);
  const [selectedNode, setSelectedNode] = useState<Node | null>(null);
  const [configPanelOpen, setConfigPanelOpen] = useState(false);
  const [validation, setValidation] = useState<ValidationResult | null>(null);

  // Sync changes back to parent
  const syncToParent = useCallback(
    (newNodes: Node[], newEdges: Edge[]) => {
      const workflowSteps = reactFlowToWorkflowSteps(newNodes, newEdges);
      onChange(workflowSteps);
    },
    [onChange]
  );

  // Update parent when nodes or edges change
  // FIX HIGH: Use debounced sync to avoid infinite loop with parent updates
  useEffect(() => {
    const timeoutId = setTimeout(() => {
      syncToParent(nodes, edges);
    }, 100);
    return () => clearTimeout(timeoutId);
  }, [nodes, edges, syncToParent]);

  // Apply validation status to nodes
  const applyValidation = useCallback(
    (validationResult: ValidationResult) => {
      setNodes((nds) =>
        nds.map((node) => {
          const nodeErrors = validationResult.errors.filter((e) => e.nodeId === node.id);
          const hasError = nodeErrors.some((e) => e.type === 'error');
          const hasWarning = nodeErrors.some((e) => e.type === 'warning');
          const messages = nodeErrors.map((e) => e.message).join('; ');
          return {
            ...node,
            data: {
              ...node.data,
              validationStatus: hasError ? 'error' : hasWarning ? 'warning' : null,
              validationMessage: messages || null,
            },
          };
        })
      );
    },
    [setNodes]
  );

  // Handle connection between nodes
  const onConnect = useCallback(
    (params: Connection) => {
      if (disabled) return;
      // CRITICAL FIX: Block self-referencing loops (AC8: infinite loops)
      if (params.source === params.target) {
        return; // Silently ignore self-connections
      }
      const sourceHandle = params.sourceHandle as string;
      const isSuccess = sourceHandle === 'success';

      // Remove existing edge from same source+handle (only one success and one error per node)
      setEdges((eds) => {
        const filtered = eds.filter(
          (e) => !(e.source === params.source && e.sourceHandle === sourceHandle)
        );
        const newEdge: Edge = {
          ...params,
          id: `${params.source}_${sourceHandle}_${params.target}`,
          type: 'smoothstep',
          animated: false,
          style: { stroke: isSuccess ? '#52c41a' : '#ff4d4f', strokeWidth: 2 },
          label: isSuccess ? 'succès' : 'erreur',
          labelStyle: { fontSize: 10, fill: isSuccess ? '#52c41a' : '#ff4d4f' },
        } as Edge;
        return addEdge(newEdge, filtered);
      });
    },
    [disabled, setEdges]
  );

  // Handle drop from palette
  const onDragOver = useCallback((event: React.DragEvent) => {
    event.preventDefault();
    event.dataTransfer.dropEffect = 'move';
  }, []);

  const onDrop = useCallback(
    (event: React.DragEvent) => {
      if (disabled) return;
      event.preventDefault();

      const actionData = event.dataTransfer.getData('application/workflow-action');
      if (!actionData) return;

      const action: ActionListItem = JSON.parse(actionData);
      const position = screenToFlowPosition({
        x: event.clientX,
        y: event.clientY,
      });

      const newNode: Node = {
        id: generateStepId(),
        type: 'workflowStep',
        position,
        data: {
          action_id: action.id,
          action_name: action.name,
          action_engine: action.engine ?? '',
          action_platform: '',
          name: null,
          retry_enabled: false,
          retry_max_attempts: null,
          retry_interval_seconds: null,
          retry_backoff_multiplier: null,
        } satisfies WorkflowStepNodeData,
      };

      setNodes((nds) => [...nds, newNode]);
    },
    [disabled, screenToFlowPosition, setNodes]
  );

  // Node double-click → open config panel
  const onNodeDoubleClick = useCallback(
    (_event: React.MouseEvent, node: Node) => {
      setSelectedNode(node);
      setConfigPanelOpen(true);
    },
    []
  );

  // Update node data from config panel
  const handleNodeUpdate = useCallback(
    (nodeId: string, updates: Partial<WorkflowStepNodeData>) => {
      setNodes((nds) =>
        nds.map((node) =>
          node.id === nodeId
            ? { ...node, data: { ...node.data, ...updates } }
            : node
        )
      );
      // Update selected node reference
      setSelectedNode((prev) =>
        prev && prev.id === nodeId
          ? { ...prev, data: { ...prev.data, ...updates } }
          : prev
      );
    },
    [setNodes]
  );

  // Delete node
  const handleNodeDelete = useCallback(
    (nodeId: string) => {
      if (disabled) return;
      // Prevent deleting the last node
      if (nodes.length <= 1) return;

      setNodes((nds) => nds.filter((n) => n.id !== nodeId));
      setEdges((eds) => eds.filter((e) => e.source !== nodeId && e.target !== nodeId));
    },
    [disabled, nodes.length, setNodes, setEdges]
  );

  // Handle nodes delete (keyboard Delete key)
  const onNodesDelete = useCallback(
    (deletedNodes: Node[]) => {
      if (disabled) return;
      // Block if it would remove all nodes
      const remaining = nodes.length - deletedNodes.length;
      if (remaining < 1) return;
    },
    [disabled, nodes.length]
  );

  // Handle edges delete
  const onEdgesDelete = useCallback(
    (_deletedEdges: Edge[]) => {
      if (disabled) return;
      // Edges are automatically removed by React Flow via onEdgesChange
    },
    [disabled]
  );

  // Run validation
  const handleValidate = useCallback(() => {
    const result = validateWorkflowGraph(nodes, edges);
    setValidation(result);
    applyValidation(result);
  }, [nodes, edges, applyValidation]);

  // Clear validation highlights
  const clearValidation = useCallback(() => {
    setValidation(null);
    setNodes((nds) =>
      nds.map((node) => ({
        ...node,
        data: {
          ...node.data,
          validationStatus: null,
          validationMessage: null,
        },
      }))
    );
  }, [setNodes]);

  return (
    <div style={{ display: 'flex', height: 600, border: `1px solid ${token.colorBorderSecondary}`, borderRadius: 8, overflow: 'hidden' }}>
      <ActionPalette disabled={disabled} />
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
        {/* Toolbar */}
        <div style={{ padding: '8px 12px', borderBottom: `1px solid ${token.colorBorderSecondary}`, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Text type="secondary" style={{ fontSize: 12 }}>
            Glissez des actions depuis la palette. Connectez les ports pour créer des branches.
          </Text>
          <Space size="small">
            <Button size="small" onClick={handleValidate} icon={<CheckCircleOutlined />}>
              Valider
            </Button>
            {validation && (
              <Button size="small" onClick={clearValidation} type="text">
                Effacer validation
              </Button>
            )}
          </Space>
        </div>

        {/* Validation summary */}
        {validation && (
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
        )}

        {/* Canvas */}
        <div ref={reactFlowWrapper} style={{ flex: 1 }}>
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={disabled ? undefined : onNodesChange}
            onEdgesChange={disabled ? undefined : onEdgesChange}
            onConnect={onConnect}
            onDrop={onDrop}
            onDragOver={onDragOver}
            onNodeDoubleClick={onNodeDoubleClick}
            onNodesDelete={onNodesDelete}
            onEdgesDelete={onEdgesDelete}
            nodeTypes={nodeTypes}
            fitView
            nodesDraggable={!disabled}
            nodesConnectable={!disabled}
            elementsSelectable={!disabled}
            connectionLineStyle={{ stroke: token.colorPrimary, strokeWidth: 2 }}
            deleteKeyCode={disabled ? null : 'Delete'}
          >
            <Controls />
            <MiniMap
              nodeStrokeWidth={3}
              pannable
              zoomable
            />
            <Background gap={16} />
          </ReactFlow>
        </div>
      </div>

      <StepConfigPanel
        node={selectedNode}
        open={configPanelOpen}
        onClose={() => setConfigPanelOpen(false)}
        onNodeUpdate={handleNodeUpdate}
        onNodeDelete={handleNodeDelete}
        disabled={disabled}
      />
    </div>
  );
}

/** WorkflowBuilderCanvas wrapped with ReactFlowProvider */
export const WorkflowBuilderCanvas: React.FC<WorkflowBuilderCanvasProps> = (props) => {
  return (
    <ReactFlowProvider>
      <WorkflowBuilderCanvasInner {...props} />
    </ReactFlowProvider>
  );
};

export default WorkflowBuilderCanvas;

/**
 * useWorkflowGraph — Graph state and event handlers for WorkflowBuilderCanvas (Story 54.12).
 *
 * Extracted from WorkflowBuilderCanvasInner.
 * Encapsulates: node/edge state, validation, event handlers, config panel state.
 *
 * IMPORTANT: Must be called inside a ReactFlowProvider context (uses useReactFlow internally).
 */

import React, { useCallback, useEffect, useMemo, useState, type Dispatch, type SetStateAction } from 'react';
import { App } from 'antd';
import {
  addEdge,
  useEdgesState,
  useNodesState,
  useReactFlow,
  type Connection,
  type Edge,
  type Node,
  type NodeChange,
  type OnEdgesChange,
  type OnNodesChange,
} from '@xyflow/react';
import { STYLE_TOKENS } from '../theme/styleTokens';
import type { WorkflowStep, ActionListItem, WorkflowStepType } from '../types/api';
import type { WorkflowStepNodeData } from '../components/admin/WorkflowStepNode';
import {
  END_NODE_ID,
  START_NODE_ID,
  generateStepId,
  reactFlowToWorkflowSteps,
  workflowStepsToReactFlow,
} from '../utils/workflowConversion';
import { getStepLabel } from '../utils/workflowStepLabels';
import { validateWorkflowGraph, type ValidationResult } from '../utils/workflowValidation';

export interface UseWorkflowGraphProps {
  steps: WorkflowStep[];
  onChange: (steps: WorkflowStep[]) => void;
  disabled?: boolean;
}

export interface UseWorkflowGraphReturn {
  // State
  nodes: Node[];
  edges: Edge[];
  selectedNode: Node | null;
  configPanelOpen: boolean;
  validation: ValidationResult | null;
  validationReportOpen: boolean;
  workflowNodeCount: number;
  // Setters needed by the component
  setConfigPanelOpen: Dispatch<SetStateAction<boolean>>;
  setValidationReportOpen: Dispatch<SetStateAction<boolean>>;
  // React Flow handlers
  onNodesChange: OnNodesChange;
  onEdgesChange: OnEdgesChange;
  onConnect: (params: Connection) => void;
  /** Story 67.4: Autorise les multi-connexions (fan-out) depuis le même handle */
  isValidConnection?: (params: Connection) => boolean;
  onDrop: (event: React.DragEvent) => void;
  onDragOver: (event: React.DragEvent) => void;
  onNodeDoubleClick: (event: React.MouseEvent, node: Node) => void;
  onNodesDelete: (deletedNodes: Node[]) => void;
  onEdgesDelete: (deletedEdges: Edge[]) => void;
  // Business handlers
  handleNodeUpdate: (nodeId: string, updates: Partial<WorkflowStepNodeData>) => void;
  handleNodeDelete: (nodeId: string) => void;
  handleValidate: () => void;
  clearValidation: () => void;
  loadImportedWorkflow: (newNodes: Node[], newEdges: Edge[]) => void;
  goToNode: (nodeId: string) => void;
  /** Story 57.13: Add a non-platform step type and open config panel */
  handleAddSpecialStep: (stepType: WorkflowStepType) => void;
  /** Story 57.13: IDs of workflow step nodes (for gate context_from) */
  workflowStepIds: string[];
  /** Story 57.19: Pre-computed step options with readable labels (for gate context_from, step_id display) */
  workflowStepOptions: { value: string; label: string }[];
}

/**
 * useWorkflowGraph — Encapsulates all graph state and event handlers.
 *
 * Must be called inside a ReactFlowProvider context.
 */
export function useWorkflowGraph({
  steps,
  onChange,
  disabled = false,
}: UseWorkflowGraphProps): UseWorkflowGraphReturn {
  const { notification } = App.useApp();
  const { screenToFlowPosition, fitView, getNode, setCenter } = useReactFlow();

  // Convert initial steps to React Flow format
  // eslint-disable-next-line react-hooks/exhaustive-deps -- Intentional: only compute on mount, steps changes handled via parent re-render
  const initial = useMemo(() => workflowStepsToReactFlow(steps), []);
  const [nodes, setNodes, onNodesChangeRaw] = useNodesState(initial.nodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initial.edges);
  const [selectedNode, setSelectedNode] = useState<Node | null>(null);
  const [configPanelOpen, setConfigPanelOpen] = useState(false);
  const [validation, setValidation] = useState<ValidationResult | null>(null);
  const [validationReportOpen, setValidationReportOpen] = useState(false);

  // Sync changes back to parent
  const syncToParent = useCallback(
    (newNodes: Node[], newEdges: Edge[]) => {
      const workflowSteps = reactFlowToWorkflowSteps(newNodes, newEdges);
      onChange(workflowSteps);
    },
    [onChange]
  );

  // Update parent when nodes or edges change (debounced)
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
      if (params.source === params.target) {
        notification.warning({
          message: 'Connexion invalide',
          description: 'Une étape ne peut pas se connecter à elle-même.',
          duration: 3,
        });
        return;
      }
      const sourceHandle = params.sourceHandle as string;
      const isSuccess = sourceHandle === 'success' || sourceHandle === 'output';

      setEdges((eds) => {
        // Story 67.4: autoriser plusieurs edges par handle (fan-out). Bloquer seulement les doublons exacts.
        const filtered = eds.filter(
          (e) => !(e.source === params.source && e.sourceHandle === sourceHandle && e.target === params.target)
        );
        const newEdge: Edge = {
          ...params,
          id: `${params.source}_${sourceHandle}_${params.target}`,
          type: 'customEdge',
          animated: false,
          style: { stroke: isSuccess ? STYLE_TOKENS.iconSuccess : STYLE_TOKENS.iconError, strokeWidth: 2 },
          label: isSuccess ? 'succès' : 'erreur',
          labelStyle: { fontSize: 10, fill: isSuccess ? STYLE_TOKENS.textSuccess : STYLE_TOKENS.textError },
        } as Edge;
        return addEdge(newEdge, filtered);
      });
    },
    [disabled, notification, setEdges]
  );

  // Story 67.4: Autoriser explicitement les multi-connexions depuis le même handle (fan-out).
  // Sans ce callback, React Flow peut bloquer la connexion avant d'appeler onConnect.
  const isValidConnection = useCallback(
    (params: Connection) => params.source !== params.target,
    []
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

      let action: ActionListItem;
      try {
        action = JSON.parse(actionData);
      } catch {
        return;
      }
      const position = screenToFlowPosition({
        x: event.clientX,
        y: event.clientY,
      });

      const newNode: Node = {
        id: generateStepId(),
        type: 'workflowStep',
        position,
        data: {
          step_type: 'platform',
          action_id: action.id,
          action_name: action.name,
          action_engine: action.engine ?? '',
          action_platform: '',
          name: null,
          retry_enabled: false,
          retry_max_attempts: null,
          retry_interval_seconds: null,
          retry_backoff_multiplier: null,
          on_success_step_id: null,
          on_error_step_id: null,
          isStartNode: false,
          isEndNode: false,
        } satisfies WorkflowStepNodeData,
      };

      setNodes((nds) => {
        const updated = [...nds, newNode];
        const existingStepNodes = nds.filter((n) => n.type === 'workflowStep');

        if (existingStepNodes.length === 0) {
          setEdges((eds) => [
            ...eds,
            {
              id: `${START_NODE_ID}_output_${newNode.id}`,
              source: START_NODE_ID,
              target: newNode.id,
              sourceHandle: 'output',
              targetHandle: 'input',
              type: 'customEdge',
              animated: false,
              style: { stroke: STYLE_TOKENS.iconSuccess, strokeWidth: 2 },
              label: 'succès',
              labelStyle: { fontSize: 10, fill: STYLE_TOKENS.textSuccess },
            } as Edge,
          ]);
        } else {
          const lastStep = existingStepNodes[existingStepNodes.length - 1];
          setEdges((eds) => {
            const lastStepHasSuccessEdge = eds.some(
              (e) => e.source === lastStep.id && e.sourceHandle === 'success'
            );
            if (lastStepHasSuccessEdge) return eds;
            return [
              ...eds,
              {
                id: `${lastStep.id}_success_${newNode.id}`,
                source: lastStep.id,
                target: newNode.id,
                sourceHandle: 'success',
                targetHandle: 'input',
                type: 'customEdge',
                animated: false,
                style: { stroke: STYLE_TOKENS.iconSuccess, strokeWidth: 2 },
                label: 'succès',
                labelStyle: { fontSize: 10, fill: STYLE_TOKENS.textSuccess },
              } as Edge,
            ];
          });
        }

        return updated;
      });
    },
    [disabled, screenToFlowPosition, setNodes, setEdges]
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
  // Sync immediately so approver_profile_ids and other config changes are included when user saves
  const handleNodeUpdate = useCallback(
    (nodeId: string, updates: Partial<WorkflowStepNodeData>) => {
      setNodes((nds) => {
        const newNodes = nds.map((node) =>
          node.id === nodeId
            ? { ...node, data: { ...node.data, ...updates } }
            : node
        );
        // Defer sync to next tick so React has applied the state update
        queueMicrotask(() => syncToParent(newNodes, edges));
        return newNodes;
      });
      setSelectedNode((prev) =>
        prev && prev.id === nodeId
          ? { ...prev, data: { ...prev.data, ...updates } }
          : prev
      );
    },
    [setNodes, syncToParent, edges]
  );

  // Count workflow nodes (exclude start/end)
  const workflowNodeCount = useMemo(
    () => nodes.filter((n) => n.id !== START_NODE_ID && n.id !== END_NODE_ID).length,
    [nodes]
  );

  // Story 57.13: IDs of workflow step nodes (for gate context_from)
  const workflowStepIds = useMemo(
    () => nodes
      .filter((n) => n.id !== START_NODE_ID && n.id !== END_NODE_ID)
      .map((n) => n.id),
    [nodes]
  );

  // Story 57.19: Pre-computed step options with readable labels (order derived from array index)
  const workflowStepOptions = useMemo(
    () => {
      const stepNodes = nodes.filter((n) => n.id !== START_NODE_ID && n.id !== END_NODE_ID);
      return stepNodes.map((n, index) => ({
        value: n.id,
        label: getStepLabel({ ...(n.data as unknown as WorkflowStepNodeData), order: index + 1 }),
      }));
    },
    [nodes]
  );

  // Story 57.13: Add a special (non-platform) step and open config panel
  const handleAddSpecialStep = useCallback(
    (stepType: WorkflowStepType) => {
      if (disabled) return;
      const stepId = generateStepId();
      const stepNodes = nodes.filter((n) => n.id !== START_NODE_ID && n.id !== END_NODE_ID);
      const newNode: Node = {
        id: stepId,
        type: 'workflowStep',
        position: { x: 200, y: stepNodes.length * 200 + 120 },
        data: {
          step_type: stepType,
          name: null,
          action_id: null,
          action_name: '',
          action_engine: '',
          action_platform: '',
          retry_enabled: false,
          retry_max_attempts: null,
          retry_interval_seconds: null,
          retry_backoff_multiplier: null,
          on_success_step_id: null,
          on_error_step_id: null,
          isStartNode: false,
          isEndNode: false,
          // Default on_timeout = FAIL for gate steps
          ...(stepType === 'gate' ? { on_timeout: 'FAIL' } : {}),
        } satisfies WorkflowStepNodeData,
      };
      setNodes((nds) => {
        const existing = nds.filter((n) => n.type === 'workflowStep');
        if (existing.length === 0) {
          // Auto-connect Start → first step
          setEdges((eds) => [
            ...eds,
            {
              id: `${START_NODE_ID}_output_${stepId}`,
              source: START_NODE_ID,
              target: stepId,
              sourceHandle: 'output',
              targetHandle: 'input',
              type: 'customEdge',
              animated: false,
              style: { stroke: STYLE_TOKENS.iconSuccess, strokeWidth: 2 },
              label: 'succès',
              labelStyle: { fontSize: 10, fill: STYLE_TOKENS.textSuccess },
            } as Edge,
          ]);
        }
        return [...nds, newNode];
      });
      // Open config panel on the new node
      setSelectedNode(newNode);
      setConfigPanelOpen(true);
    },
    [disabled, nodes, setNodes, setEdges]
  );

  const handleNodeDelete = useCallback(
    (nodeId: string) => {
      if (disabled) return;
      if (nodeId === START_NODE_ID || nodeId === END_NODE_ID) return;
      if (workflowNodeCount <= 1) return;

      setNodes((nds) => nds.filter((n) => n.id !== nodeId));
      setEdges((eds) => eds.filter((e) => e.source !== nodeId && e.target !== nodeId));
    },
    [disabled, workflowNodeCount, setNodes, setEdges]
  );

  // Guarded onNodesChange: prevents deletion of the last workflow step via keyboard Delete.
  // Start/End nodes are already non-deletable via `deletable: false` in their node config.
  const onNodesChange: OnNodesChange = useCallback(
    (changes: NodeChange[]) => {
      const workflowRemoveCount = changes.filter(
        (c) => c.type === 'remove' && c.id !== START_NODE_ID && c.id !== END_NODE_ID
      ).length;
      if (workflowRemoveCount > 0 && workflowNodeCount - workflowRemoveCount < 1) {
        // Block removal to preserve minimum 1 workflow step
        const safeChanges = changes.filter(
          (c) => !(c.type === 'remove' && c.id !== START_NODE_ID && c.id !== END_NODE_ID)
        );
        onNodesChangeRaw(safeChanges);
        return;
      }
      onNodesChangeRaw(changes);
    },
    [onNodesChangeRaw, workflowNodeCount]
  );

  // onNodesDelete is called after deletion.
  // Start/End are protected by deletable:false; last-step guard is in onNodesChange.
  const onNodesDelete = useCallback((_deletedNodes: Node[]) => { /* no-op */ }, []);

  // Handle edges delete — edge state is auto-managed by useEdgesState; no action needed.
  const onEdgesDelete = useCallback((_deletedEdges: Edge[]) => { /* no-op */ }, []);

  // Run validation and open report panel
  const handleValidate = useCallback(() => {
    const result = validateWorkflowGraph(nodes, edges);
    setValidation(result);
    applyValidation(result);
    setValidationReportOpen(true);
  }, [nodes, edges, applyValidation]);

  // Clear validation highlights
  const clearValidation = useCallback(() => {
    setValidation(null);
    setValidationReportOpen(false);
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

  // Load imported workflow (replaces nodes/edges)
  const loadImportedWorkflow = useCallback((newNodes: Node[], newEdges: Edge[]) => {
    setValidation(null);
    setValidationReportOpen(false);
    setNodes(newNodes);
    setEdges(newEdges);
    requestAnimationFrame(() => {
      fitView({ padding: 0.2, duration: 500 });
    });
  }, [setNodes, setEdges, fitView]);

  // Navigate to a specific node (for validation report)
  const goToNode = useCallback(
    (nodeId: string) => {
      const node = getNode(nodeId);
      if (!node) return;
      setCenter(node.position.x + 100, node.position.y + 50, { zoom: 1.2, duration: 800 });
      setNodes((nds) => nds.map((n) => ({ ...n, selected: n.id === nodeId })));
    },
    [getNode, setCenter, setNodes]
  );

  return {
    nodes,
    edges,
    selectedNode,
    configPanelOpen,
    validation,
    validationReportOpen,
    workflowNodeCount,
    setConfigPanelOpen,
    setValidationReportOpen,
    onNodesChange,
    onEdgesChange,
    onConnect,
    isValidConnection,
    onDrop,
    onDragOver,
    onNodeDoubleClick,
    onNodesDelete,
    onEdgesDelete,
    handleNodeUpdate,
    handleNodeDelete,
    handleValidate,
    clearValidation,
    loadImportedWorkflow,
    goToNode,
    handleAddSpecialStep,
    workflowStepIds,
    workflowStepOptions,
  };
}

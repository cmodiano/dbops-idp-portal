/**
 * WorkflowBuilderCanvas — Visual workflow builder using React Flow (Story 16.5, 16.7).
 *
 * Features:
 * - Zoomable/pannable canvas (AC1)
 * - Drag-and-drop actions from palette (AC2)
 * - Success/error connections between nodes (AC3, AC4)
 * - Step configuration panel (AC5)
 * - Node and edge deletion (AC6, AC7)
 * - Workflow validation with visual feedback (AC8)
 * - Bidirectional sync with WorkflowStep[] (Task 7)
 * - Start/End visual nodes (Story 16.7, AC1)
 * - Interactive edges with context menu (Story 16.7, AC5)
 * - Validation report panel (Story 16.7, AC7)
 * - Save blocking on validation errors (Story 16.7, AC8)
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
import { Alert, App, Button, Dropdown, Modal, Space, theme, Typography, List } from 'antd';
import {
  CheckCircleOutlined,
  CloseCircleOutlined,
  ExportOutlined,
  FileTextOutlined,
  ImportOutlined,
  PictureOutlined,
  WarningOutlined,
} from '@ant-design/icons';
import type { WorkflowStep, ActionListItem } from '../../types/api';
import {
  exportWorkflowAsJSON,
  exportWorkflowAsYAML,
  exportWorkflowAsImage,
  parseWorkflowFile,
  type WorkflowMetadata,
} from '../../utils/workflowExport';
import WorkflowStepNode, { type WorkflowStepNodeData } from './WorkflowStepNode';
import StartNode from './StartNode';
import EndNode from './EndNode';
import CustomEdge from './CustomEdge';
import { ActionPalette } from './ActionPalette';
import { StepConfigPanel } from './StepConfigPanel';
import ValidationReportPanel from './ValidationReportPanel';
import logger from '../../services/logger';

const { Text } = Typography;

// ── Data conversion utilities ──────────────────────────────────────────────

function generateStepId(): string {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID();
  }
  return `step-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

// IDs for visual-only start/end nodes
export const START_NODE_ID = '__start__';
export const END_NODE_ID = '__end__';

/** Convert WorkflowStep[] → React Flow nodes + edges (with start/end visual nodes) */
export function workflowStepsToReactFlow(
  steps: WorkflowStep[],
): { nodes: Node[]; edges: Edge[] } {
  const workflowNodes: Node[] = steps.map((step, index) => ({
    id: step.step_id ?? `step-${index}`,
    type: 'workflowStep',
    position: { x: (index % 4) * 280, y: Math.floor(index / 4) * 200 + 120 },
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
      on_success_step_id: step.on_success_step_id ?? null,
      on_error_step_id: step.on_error_step_id ?? null,
      on_success_step_name: step.on_success_step_id
        ? steps.find((s) => s.step_id === step.on_success_step_id)?.name ?? null
        : null,
      on_error_step_name: step.on_error_step_id
        ? steps.find((s) => s.step_id === step.on_error_step_id)?.name ?? null
        : null,
      isStartNode: false,
      isEndNode: false,
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
        type: 'customEdge',
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
        type: 'customEdge',
        animated: false,
        style: { stroke: '#ff4d4f', strokeWidth: 2 },
        label: 'erreur',
        labelStyle: { fontSize: 10, fill: '#ff4d4f' },
      });
    }
  });

  // Inject visual start node
  const startNode: Node = {
    id: START_NODE_ID,
    type: 'start',
    position: { x: 0, y: 0 },
    data: { isStartNode: true },
    draggable: false,
    selectable: false,
    deletable: false,
  };

  // Compute end node position below all workflow nodes
  const maxY = workflowNodes.length > 0
    ? Math.max(...workflowNodes.map((n) => n.position.y)) + 200
    : 120;
  const endNode: Node = {
    id: END_NODE_ID,
    type: 'end',
    position: { x: 0, y: maxY },
    data: { isEndNode: true },
    draggable: false,
    selectable: false,
    deletable: false,
  };

  // Connect start → first workflow node
  if (workflowNodes.length > 0) {
    edges.push({
      id: `${START_NODE_ID}_to_${workflowNodes[0].id}`,
      source: START_NODE_ID,
      sourceHandle: 'output',
      target: workflowNodes[0].id,
      targetHandle: 'input',
      type: 'customEdge',
      animated: false,
      style: { stroke: '#52c41a', strokeWidth: 2, strokeDasharray: '5,5' },
      deletable: false,
      selectable: false,
    });
  }

  // Connect nodes without any output to end node
  const nodesWithOutput = new Set(edges.map((e) => e.source));
  workflowNodes.forEach((node) => {
    if (!nodesWithOutput.has(node.id)) {
      edges.push({
        id: `${node.id}_to_${END_NODE_ID}`,
        source: node.id,
        sourceHandle: 'success',
        target: END_NODE_ID,
        targetHandle: 'input',
        type: 'customEdge',
        animated: false,
        style: { stroke: '#8c8c8c', strokeWidth: 1, strokeDasharray: '5,5' },
        deletable: false,
        selectable: false,
      });
    }
  });

  return { nodes: [startNode, ...workflowNodes, endNode], edges };
}

/** Convert React Flow nodes + edges → WorkflowStep[] (excludes start/end visual nodes) */
export function reactFlowToWorkflowSteps(
  nodes: Node[],
  edges: Edge[],
): WorkflowStep[] {
  // Filter out start/end visual nodes
  const workflowNodes = nodes.filter(
    (n) => n.id !== START_NODE_ID && n.id !== END_NODE_ID
  );

  return workflowNodes.map((node, index) => {
    const data = node.data as unknown as WorkflowStepNodeData;
    const successEdge = edges.find(
      (e) => e.source === node.id && e.sourceHandle === 'success' && e.target !== END_NODE_ID
    );
    const errorEdge = edges.find(
      (e) => e.source === node.id && e.sourceHandle === 'error' && e.target !== END_NODE_ID
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
  // Filter out start/end visual nodes for validation
  const workflowNodes = nodes.filter(
    (n) => n.id !== START_NODE_ID && n.id !== END_NODE_ID
  );
  const workflowEdges = edges.filter(
    (e) => e.source !== START_NODE_ID && e.target !== END_NODE_ID &&
          e.source !== END_NODE_ID && e.target !== START_NODE_ID
  );

  const errors: ValidationError[] = [];

  if (workflowNodes.length === 0) {
    return { valid: false, errors: [{ nodeId: '', type: 'error', message: 'Au moins une étape est requise' }] };
  }

  // 1. Check every node has at least one output connection
  workflowNodes.forEach((node) => {
    const hasSuccessEdge = workflowEdges.some((e) => e.source === node.id && e.sourceHandle === 'success');
    const hasErrorEdge = workflowEdges.some((e) => e.source === node.id && e.sourceHandle === 'error');

    if (!hasSuccessEdge && !hasErrorEdge) {
      errors.push({
        nodeId: node.id,
        type: 'warning',
        message: `Pas de chemin de sortie`,
      });
    }
  });

  // 2. Detect orphan nodes (not reachable from start)
  if (workflowNodes.length > 1) {
    const reachableNodes = new Set<string>();
    const startNode = workflowNodes[0];
    const queue = [startNode.id];

    while (queue.length > 0) {
      const current = queue.shift()!;
      if (reachableNodes.has(current)) continue;
      reachableNodes.add(current);

      workflowEdges
        .filter((e) => e.source === current)
        .forEach((e) => {
          if (!reachableNodes.has(e.target)) {
            queue.push(e.target);
          }
        });
    }

    workflowNodes.forEach((node) => {
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

    const outEdges = workflowEdges.filter((e) => e.source === nodeId);
    for (const edge of outEdges) {
      if (dfs(edge.target)) {
        loopNodes.add(nodeId);
      }
    }

    inStack.delete(nodeId);
    return false;
  }

  workflowNodes.forEach((node) => {
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

// ── Node & edge types registration ──────────────────────────────────────────

const nodeTypes = {
  workflowStep: WorkflowStepNode,
  start: StartNode,
  end: EndNode,
};

const edgeTypes = {
  customEdge: CustomEdge,
};

// ── Main component ─────────────────────────────────────────────────────────

export interface WorkflowBuilderCanvasProps {
  steps: WorkflowStep[];
  onChange: (steps: WorkflowStep[]) => void;
  disabled?: boolean;
  /** Workflow metadata for export (name, description, tags). Story 16.8. */
  workflowMetadata?: WorkflowMetadata;
  /** Callback when import replaces metadata (name, description, tags). Story 16.8. */
  onMetadataImport?: (metadata: WorkflowMetadata) => void;
}

function WorkflowBuilderCanvasInner({
  steps,
  onChange,
  disabled = false,
  workflowMetadata,
  onMetadataImport,
}: WorkflowBuilderCanvasProps) {
  const { token } = theme.useToken();
  const { notification } = App.useApp();
  const reactFlowWrapper = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const { screenToFlowPosition, fitView } = useReactFlow();
  const [exporting, setExporting] = useState(false);

  // Convert initial steps to React Flow format
  const initial = useMemo(() => workflowStepsToReactFlow(steps), []);
  const [nodes, setNodes, onNodesChange] = useNodesState(initial.nodes);
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
        notification.warning({
          message: 'Connexion invalide',
          description: 'Une étape ne peut pas se connecter à elle-même.',
          duration: 3,
        });
        return;
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
          type: 'customEdge',
          animated: false,
          style: { stroke: isSuccess ? '#52c41a' : '#ff4d4f', strokeWidth: 2 },
          label: isSuccess ? 'succès' : 'erreur',
          labelStyle: { fontSize: 10, fill: isSuccess ? '#52c41a' : '#ff4d4f' },
        } as Edge;
        return addEdge(newEdge, filtered);
      });
    },
    [disabled, notification, setEdges]
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
          on_success_step_id: null,
          on_error_step_id: null,
          isStartNode: false,
          isEndNode: false,
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

  // Delete node (exclude start/end from count)
  const workflowNodeCount = useMemo(
    () => nodes.filter((n) => n.id !== START_NODE_ID && n.id !== END_NODE_ID).length,
    [nodes]
  );

  const handleNodeDelete = useCallback(
    (nodeId: string) => {
      if (disabled) return;
      // Prevent deleting start/end nodes
      if (nodeId === START_NODE_ID || nodeId === END_NODE_ID) return;
      // Prevent deleting the last workflow node
      if (workflowNodeCount <= 1) return;

      setNodes((nds) => nds.filter((n) => n.id !== nodeId));
      setEdges((eds) => eds.filter((e) => e.source !== nodeId && e.target !== nodeId));
    },
    [disabled, workflowNodeCount, setNodes, setEdges]
  );

  // Handle nodes delete (keyboard Delete key)
  const onNodesDelete = useCallback(
    (deletedNodes: Node[]) => {
      if (disabled) return;
      // Filter out start/end from deletion candidates
      const actualDeleted = deletedNodes.filter(
        (n) => n.id !== START_NODE_ID && n.id !== END_NODE_ID
      );
      const remaining = workflowNodeCount - actualDeleted.length;
      if (remaining < 1) return;
    },
    [disabled, workflowNodeCount]
  );

  // Handle edges delete
  const onEdgesDelete = useCallback(
    (_deletedEdges: Edge[]) => {
      if (disabled) return;
      // Edges are automatically removed by React Flow via onEdgesChange
    },
    [disabled]
  );

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

  // ── Story 16.8: Export/Import handlers ─────────────────────────────────

  const getMetadata = useCallback((): WorkflowMetadata => {
    return workflowMetadata ?? { name: 'workflow', description: null, tags: [] };
  }, [workflowMetadata]);

  const handleExportJSON = useCallback(() => {
    const currentSteps = reactFlowToWorkflowSteps(nodes, edges);
    // MEDIUM-2 FIX: Add debug logging for troubleshooting
    logger.debug('Export JSON', { stepCount: currentSteps.length, workflowName: getMetadata().name });
    exportWorkflowAsJSON(currentSteps, getMetadata());
    notification.success({ message: 'Export JSON réussi', duration: 3 });
  }, [nodes, edges, getMetadata, notification]);

  const handleExportYAML = useCallback(() => {
    const currentSteps = reactFlowToWorkflowSteps(nodes, edges);
    // MEDIUM-2 FIX: Add debug logging for troubleshooting
    logger.debug('Export YAML', { stepCount: currentSteps.length, workflowName: getMetadata().name });
    exportWorkflowAsYAML(currentSteps, getMetadata());
    notification.success({ message: 'Export YAML réussi', duration: 3 });
  }, [nodes, edges, getMetadata, notification]);

  const handleExportImage = useCallback(async () => {
    if (!reactFlowWrapper.current) return;
    setExporting(true);
    try {
      await exportWorkflowAsImage(reactFlowWrapper.current, getMetadata().name);
      notification.success({ message: 'Export image réussi', duration: 3 });
    } catch (err) {
      // MEDIUM-3 FIX: Include error details for better troubleshooting
      const errorMessage = err instanceof Error ? err.message : 'Erreur inconnue';
      notification.error({
        message: 'Erreur lors de l\'export image',
        description: errorMessage,
        duration: 5,
      });
      logger.error('Export image error', { error: err instanceof Error ? err.message : String(err) });
    } finally {
      setExporting(false);
    }
  }, [getMetadata, notification]);

  const exportMenuItems = useMemo(() => [
    { key: 'json', label: 'Exporter en JSON', icon: <ExportOutlined />, onClick: handleExportJSON },
    { key: 'yaml', label: 'Exporter en YAML', icon: <FileTextOutlined />, onClick: handleExportYAML },
    { key: 'image', label: 'Exporter l\'image', icon: <PictureOutlined />, onClick: handleExportImage },
  ], [handleExportJSON, handleExportYAML, handleExportImage]);

  const loadImportedWorkflow = useCallback((importData: NonNullable<ReturnType<typeof parseWorkflowFile>['data']>) => {
    const { nodes: newNodes, edges: newEdges } = workflowStepsToReactFlow(importData.workflow.steps);

    // MEDIUM-2 FIX: Add debug logging for troubleshooting
    logger.debug('Workflow imported', { stepCount: importData.workflow.steps.length, workflowName: importData.workflow.name });

    // HIGH-5 FIX: Use setState callback to ensure fitView runs after render
    // HIGH-6 FIX: Clear validation state when importing new workflow
    setValidation(null);
    setValidationReportOpen(false);

    setNodes(newNodes);
    setEdges(newEdges);

    // Use requestAnimationFrame to ensure React Flow has rendered nodes before fitView
    requestAnimationFrame(() => {
      fitView({ padding: 0.2, duration: 500 });
    });

    if (onMetadataImport) {
      onMetadataImport({
        name: importData.workflow.name,
        description: importData.workflow.description,
        tags: importData.workflow.tags,
      });
    }
    notification.success({ message: 'Workflow importé avec succès', duration: 3 });
  }, [setNodes, setEdges, fitView, onMetadataImport, notification, setValidation, setValidationReportOpen]);

  const handleImportFile = useCallback((event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    // HIGH-2 FIX: Validate file size (max 5MB)
    const maxSizeBytes = 5 * 1024 * 1024; // 5MB
    if (file.size > maxSizeBytes) {
      notification.error({
        message: 'Fichier trop volumineux',
        description: `La taille maximale autorisée est de 5 MB. Votre fichier fait ${(file.size / 1024 / 1024).toFixed(2)} MB.`,
        duration: 5,
      });
      event.target.value = ''; // Reset input
      return;
    }

    const extension = '.' + file.name.split('.').pop()?.toLowerCase();
    const reader = new FileReader();

    reader.onload = (e) => {
      const content = e.target?.result as string;
      if (!content) {
        notification.error({ message: 'Le fichier est vide', duration: 5 });
        return;
      }

      const result = parseWorkflowFile(content, extension);
      if (!result.valid || !result.data) {
        Modal.error({
          title: 'Format de fichier invalide',
          width: 600,
          content: (
            <List
              size="small"
              dataSource={result.errors}
              renderItem={(err) => (
                <List.Item>
                  <CloseCircleOutlined style={{ color: '#ff4d4f', marginRight: 8 }} />
                  {err}
                </List.Item>
              )}
            />
          ),
          okText: 'Compris',
        });
        return;
      }

      const importData = result.data;

      // Check if current workflow has nodes → confirm replacement
      const currentWorkflowNodes = nodes.filter(
        (n) => n.id !== START_NODE_ID && n.id !== END_NODE_ID
      );
      if (currentWorkflowNodes.length > 0) {
        Modal.confirm({
          title: 'Remplacer le workflow actuel ?',
          content: 'Le workflow actuel sera remplacé par le workflow importé. Cette action est irréversible.',
          okText: 'Remplacer',
          okButtonProps: { danger: true },
          cancelText: 'Annuler',
          onOk: () => loadImportedWorkflow(importData),
        });
      } else {
        loadImportedWorkflow(importData);
      }
    };

    reader.onerror = () => {
      notification.error({ message: 'Erreur lors de la lecture du fichier', duration: 5 });
    };

    reader.readAsText(file);
    // Reset input so the same file can be re-imported
    event.target.value = '';
  }, [nodes, notification, loadImportedWorkflow]);

  // Navigate to a specific node (for validation report)
  const { getNode, setCenter } = useReactFlow();
  const goToNode = useCallback(
    (nodeId: string) => {
      const node = getNode(nodeId);
      if (!node) return;
      setCenter(node.position.x + 100, node.position.y + 50, { zoom: 1.2, duration: 800 });
      setNodes((nds) => nds.map((n) => ({ ...n, selected: n.id === nodeId })));
    },
    [getNode, setCenter, setNodes]
  );

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
            <Button
              size="small"
              icon={<ImportOutlined />}
              onClick={() => fileInputRef.current?.click()}
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
            <Button size="small" onClick={handleValidate} icon={<CheckCircleOutlined />}>
              Valider le workflow
            </Button>
            {validation && (
              <>
                <Button size="small" onClick={() => setValidationReportOpen(true)} type="default">
                  Voir le rapport
                </Button>
                <Button size="small" onClick={clearValidation} type="text">
                  Effacer validation
                </Button>
              </>
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
            edgeTypes={edgeTypes}
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

      <ValidationReportPanel
        validation={validation}
        open={validationReportOpen}
        onClose={() => setValidationReportOpen(false)}
        onGoToNode={goToNode}
      />

      {/* Story 16.8: Hidden file input for import */}
      <input
        ref={fileInputRef}
        type="file"
        accept=".json,.yaml,.yml"
        onChange={handleImportFile}
        style={{ display: 'none' }}
        aria-label="Sélectionner un fichier workflow à importer"
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

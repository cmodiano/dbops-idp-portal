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
 *
 * Refactored in Story 26.5: conversion, validation, export/import, toolbar, alert extracted.
 */

import React, { useCallback, useMemo, useState, useRef, useEffect } from 'react';
import { STYLE_TOKENS } from '../../theme/styleTokens';
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
import { App, theme } from 'antd';
import type { WorkflowStep, ActionListItem } from '../../types/api';
import type { WorkflowMetadata } from '../../utils/workflowExport';
import type { WorkflowStepNodeData } from './WorkflowStepNode';
import {
  generateStepId,
  START_NODE_ID,
  END_NODE_ID,
  workflowStepsToReactFlow,
  reactFlowToWorkflowSteps,
} from '../../utils/workflowConversion';
import { validateWorkflowGraph, type ValidationResult } from '../../utils/workflowValidation';
import { useWorkflowExportImport } from '../../hooks/useWorkflowExportImport';
import { WorkflowBuilderToolbar } from '../workflow/WorkflowBuilderToolbar';
import { WorkflowValidationAlert } from '../workflow/WorkflowValidationAlert';
import WorkflowStepNode from './WorkflowStepNode';
import StartNode from './StartNode';
import EndNode from './EndNode';
import CustomEdge from './CustomEdge';
import { ActionPalette } from './ActionPalette';
import { StepConfigPanel } from './StepConfigPanel';
import ValidationReportPanel from './ValidationReportPanel';

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
  const { screenToFlowPosition, fitView } = useReactFlow();

  // Convert initial steps to React Flow format
  // eslint-disable-next-line react-hooks/exhaustive-deps -- Intentional: only compute on mount, steps changes handled via parent re-render
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
        const filtered = eds.filter(
          (e) => !(e.source === params.source && e.sourceHandle === sourceHandle)
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
  const handleNodeUpdate = useCallback(
    (nodeId: string, updates: Partial<WorkflowStepNodeData>) => {
      setNodes((nds) =>
        nds.map((node) =>
          node.id === nodeId
            ? { ...node, data: { ...node.data, ...updates } }
            : node
        )
      );
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
      if (nodeId === START_NODE_ID || nodeId === END_NODE_ID) return;
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
    () => {
      if (disabled) return;
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

  // Export/import hook (Story 26.5 AC3)
  const loadImportedWorkflow = useCallback((newNodes: Node[], newEdges: Edge[]) => {
    setValidation(null);
    setValidationReportOpen(false);
    setNodes(newNodes);
    setEdges(newEdges);
    requestAnimationFrame(() => {
      fitView({ padding: 0.2, duration: 500 });
    });
  }, [setNodes, setEdges, fitView]);

  const {
    exporting,
    handleImportFile,
    fileInputRef,
    exportMenuItems,
  } = useWorkflowExportImport({
    nodes,
    edges,
    metadata: workflowMetadata,
    reactFlowWrapperRef: reactFlowWrapper,
    onMetadataImport,
    onWorkflowLoad: loadImportedWorkflow,
    onClearValidation: clearValidation,
  });

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
    <div style={{ display: 'flex', height: 700, border: `1px solid ${token.colorBorderSecondary}`, borderRadius: 8, overflow: 'hidden' }}>
      <ActionPalette disabled={disabled} />
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
        <WorkflowBuilderToolbar
          disabled={disabled}
          exporting={exporting}
          validation={validation}
          exportMenuItems={exportMenuItems}
          onImportClick={() => fileInputRef.current?.click()}
          onValidate={handleValidate}
          onShowReport={() => setValidationReportOpen(true)}
          onClearValidation={clearValidation}
        />

        <WorkflowValidationAlert validation={validation} />

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

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
 * Refactored in Story 54.12: graph state and event handlers extracted to useWorkflowGraph.
 */

import { useRef, useMemo } from 'react';
import type { FC } from 'react';
import {
  ReactFlow,
  Controls,
  Background,
  MiniMap,
  ReactFlowProvider,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { theme } from 'antd';
import type { WorkflowStep } from '../../types/api';
import type { WorkflowMetadata } from '../../utils/workflowExport';
import { useWorkflowGraph } from '../../hooks/useWorkflowGraph';
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
  /** Story 63.3: ID du workflow pour le VariablePicker. */
  workflowId?: number;
}

function WorkflowBuilderCanvasInner({
  steps,
  onChange,
  disabled = false,
  workflowMetadata,
  onMetadataImport,
  workflowId,
}: WorkflowBuilderCanvasProps) {
  const { token } = theme.useToken();
  const reactFlowWrapper = useRef<HTMLDivElement>(null);

  // Hook appelle useReactFlow() → doit être dans le provider
  const graph = useWorkflowGraph({ steps, onChange, disabled });

  // Story 67.4: Calculer le nombre de connexions entrantes du node sélectionné
  const selectedNodeIncomingEdgeCount = useMemo(
    () => graph.selectedNode ? graph.edges.filter(e => e.target === graph.selectedNode!.id).length : 0,
    [graph.edges, graph.selectedNode],
  );

  const {
    exporting,
    handleImportFile,
    fileInputRef,
    exportMenuItems,
  } = useWorkflowExportImport({
    nodes: graph.nodes,
    edges: graph.edges,
    metadata: workflowMetadata,
    reactFlowWrapperRef: reactFlowWrapper,
    onMetadataImport,
    onWorkflowLoad: graph.loadImportedWorkflow,
    onClearValidation: graph.clearValidation,
  });

  return (
    <div style={{ display: 'flex', height: 700, border: `1px solid ${token.colorBorderSecondary}`, borderRadius: 8, overflow: 'hidden' }}>
      <ActionPalette disabled={disabled} onAddSpecialStep={graph.handleAddSpecialStep} />
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
        <WorkflowBuilderToolbar
          disabled={disabled}
          exporting={exporting}
          validation={graph.validation}
          exportMenuItems={exportMenuItems}
          onImportClick={() => fileInputRef.current?.click()}
          onValidate={graph.handleValidate}
          onShowReport={() => graph.setValidationReportOpen(true)}
          onClearValidation={graph.clearValidation}
        />

        <WorkflowValidationAlert validation={graph.validation} />

        {/* Canvas */}
        <div ref={reactFlowWrapper} style={{ flex: 1 }}>
          <ReactFlow
            nodes={graph.nodes}
            edges={graph.edges}
            onNodesChange={disabled ? undefined : graph.onNodesChange}
            onEdgesChange={disabled ? undefined : graph.onEdgesChange}
            onConnect={graph.onConnect}
            onDrop={graph.onDrop}
            onDragOver={graph.onDragOver}
            onNodeDoubleClick={graph.onNodeDoubleClick}
            onNodesDelete={graph.onNodesDelete}
            onEdgesDelete={graph.onEdgesDelete}
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
        node={graph.selectedNode}
        open={graph.configPanelOpen}
        onClose={() => graph.setConfigPanelOpen(false)}
        onNodeUpdate={graph.handleNodeUpdate}
        onNodeDelete={graph.handleNodeDelete}
        disabled={disabled}
        availableStepIds={graph.workflowStepIds}
        availableStepOptions={graph.workflowStepOptions}
        workflowId={workflowId}
        incomingEdgeCount={selectedNodeIncomingEdgeCount}
      />

      <ValidationReportPanel
        validation={graph.validation}
        open={graph.validationReportOpen}
        onClose={() => graph.setValidationReportOpen(false)}
        onGoToNode={graph.goToNode}
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
export const WorkflowBuilderCanvas: FC<WorkflowBuilderCanvasProps> = (props) => {
  return (
    <ReactFlowProvider>
      <WorkflowBuilderCanvasInner {...props} />
    </ReactFlowProvider>
  );
};

export default WorkflowBuilderCanvas;

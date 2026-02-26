/**
 * Workflow Conversion Utilities — Story 26.5 AC1
 *
 * Extracted from WorkflowBuilderCanvas.tsx to separate concerns.
 * Converts between WorkflowStep[] (API format) and React Flow nodes/edges format.
 */
import type { Node, Edge } from '@xyflow/react';
import type { WorkflowStep } from '../types/api';
import type { WorkflowStepNodeData } from '../components/admin/WorkflowStepNode';
import { STYLE_TOKENS } from '../theme/styleTokens';

/** Generate unique step ID using crypto.randomUUID or fallback. */
export function generateStepId(): string {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID();
  }
  return `step-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

/** IDs for visual-only start/end nodes. */
export const START_NODE_ID = '__start__';
export const END_NODE_ID = '__end__';

// Grid layout constants for node positioning
const GRID_SPACING_X = 280;
const GRID_SPACING_Y = 200;
const START_OFFSET_Y = 120;
const END_NODE_OFFSET_Y = 200;

/** Convert WorkflowStep[] → React Flow nodes + edges (with start/end visual nodes) */
export function workflowStepsToReactFlow(
  steps: WorkflowStep[],
): { nodes: Node[]; edges: Edge[] } {
  const workflowNodes: Node[] = steps.map((step, index) => ({
    id: step.step_id ?? `step-${index}`,
    type: 'workflowStep',
    position: { x: (index % 4) * GRID_SPACING_X, y: Math.floor(index / 4) * GRID_SPACING_Y + START_OFFSET_Y },
    data: {
      action_id: step.referenced_action_id,
      action_name: step.action_name ?? `Action #${step.referenced_action_id}`,
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
        style: { stroke: STYLE_TOKENS.iconSuccess, strokeWidth: 2 },
        label: 'succès',
        labelStyle: { fontSize: 10, fill: STYLE_TOKENS.textSuccess },
      });
    } else {
      // on_success_step_id=null means "end of workflow" — draw edge to End node for clarity
      edges.push({
        id: `${sourceId}_success_${END_NODE_ID}`,
        source: sourceId,
        target: END_NODE_ID,
        sourceHandle: 'success',
        targetHandle: 'input',
        type: 'customEdge',
        animated: false,
        style: { stroke: STYLE_TOKENS.iconSuccess, strokeWidth: 2 },
        label: 'succès',
        labelStyle: { fontSize: 10, fill: STYLE_TOKENS.textSuccess },
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
        labelStyle: { fontSize: 10, fill: STYLE_TOKENS.textError },
      });
    } else {
      // on_error_step_id=null means "end/fail" — draw edge to End node for clarity
      edges.push({
        id: `${sourceId}_error_${END_NODE_ID}`,
        source: sourceId,
        target: END_NODE_ID,
        sourceHandle: 'error',
        targetHandle: 'input',
        type: 'customEdge',
        animated: false,
        style: { stroke: '#ff4d4f', strokeWidth: 2 },
        label: 'erreur',
        labelStyle: { fontSize: 10, fill: STYLE_TOKENS.textError },
      });
    }
  });

  // Inject visual start node (Story 18.3: draggable: true for repositioning)
  const startNode: Node = {
    id: START_NODE_ID,
    type: 'start',
    position: { x: 0, y: 0 },
    data: { isStartNode: true },
    draggable: true,
    selectable: false,
    deletable: false,
  };

  // Compute end node position below all workflow nodes
  const maxY = workflowNodes.length > 0
    ? Math.max(...workflowNodes.map((n) => n.position.y)) + END_NODE_OFFSET_Y
    : START_OFFSET_Y;
  const endNode: Node = {
    id: END_NODE_ID,
    type: 'end',
    position: { x: 0, y: maxY },
    data: { isEndNode: true },
    draggable: true,
    selectable: false,
    deletable: false,
  };

  // Auto-connect Start → first step and steps with null → End for correct display when loading
  if (workflowNodes.length > 0) {
    const firstStepId = steps[0]?.step_id ?? workflowNodes[0].id;
    if (firstStepId) {
      edges.push({
        id: `${START_NODE_ID}_output_${firstStepId}`,
        source: START_NODE_ID,
        target: firstStepId,
        sourceHandle: 'output',
        targetHandle: 'input',
        type: 'customEdge',
        animated: false,
        style: { stroke: STYLE_TOKENS.iconSuccess, strokeWidth: 2 },
        label: 'succès',
        labelStyle: { fontSize: 10, fill: STYLE_TOKENS.textSuccess },
      });
    }
  }

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

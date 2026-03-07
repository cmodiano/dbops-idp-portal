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
// Story 57.13: WorkflowStepType imported for backward compat default
import type { WorkflowStepType } from '../types/api';

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
      // platform fields
      action_id: step.referenced_action_id ?? null,
      action_name: step.action_name ?? (step.referenced_action_id ? `Action #${step.referenced_action_id}` : ''),
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
      // Story 57.13: step type and type-specific fields
      step_type: step.step_type ?? 'platform',
      integration_type: step.integration_type ?? null,
      operation: step.operation ?? null,
      policy_id: step.policy_id ?? null,
      gate_type: step.gate_type ?? null,
      on_timeout: step.on_timeout ?? null,
      context_from: step.context_from ?? null,
      approver_profile_ids: step.approver_profile_ids ?? null,
      timeout: step.timeout ?? null,
      url: step.url ?? null,
      method: step.method ?? null,
      headers: step.headers ?? null,
      request_timeout: step.request_timeout ?? null,
      condition: step.condition ?? null,
      input_mapping: step.input_mapping ?? null,
      output_mapping: step.output_mapping ?? null,
      // Story 57.16: schedule_execution
      schedule_config: step.schedule_config ?? null,
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
        style: { stroke: STYLE_TOKENS.iconSuccess, strokeWidth: STYLE_TOKENS.edgeStrokeWidth },
        label: 'succès',
        labelStyle: { fontSize: STYLE_TOKENS.edgeLabelFontSize, fill: STYLE_TOKENS.textSuccess },
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
        style: { stroke: STYLE_TOKENS.iconSuccess, strokeWidth: STYLE_TOKENS.edgeStrokeWidth },
        label: 'succès',
        labelStyle: { fontSize: STYLE_TOKENS.edgeLabelFontSize, fill: STYLE_TOKENS.textSuccess },
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
        style: { stroke: STYLE_TOKENS.iconError, strokeWidth: STYLE_TOKENS.edgeStrokeWidth },
        label: 'erreur',
        labelStyle: { fontSize: STYLE_TOKENS.edgeLabelFontSize, fill: STYLE_TOKENS.textError },
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
        style: { stroke: STYLE_TOKENS.iconError, strokeWidth: STYLE_TOKENS.edgeStrokeWidth },
        label: 'erreur',
        labelStyle: { fontSize: STYLE_TOKENS.edgeLabelFontSize, fill: STYLE_TOKENS.textError },
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
        style: { stroke: STYLE_TOKENS.iconSuccess, strokeWidth: STYLE_TOKENS.edgeStrokeWidth },
        label: 'succès',
        labelStyle: { fontSize: STYLE_TOKENS.edgeLabelFontSize, fill: STYLE_TOKENS.textSuccess },
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

    // Story 57.13: backward compat — default to 'platform' if step_type not set
    const stepType: WorkflowStepType = data.step_type ?? 'platform';

    const baseStep: WorkflowStep = {
      order: index + 1,
      step_id: node.id,
      step_type: stepType,
      name: data.name ?? null,
      on_success_step_id: successEdge?.target ?? null,
      on_error_step_id: errorEdge?.target ?? null,
      // shared
      condition: data.condition ?? null,
    };

    if (stepType === 'platform' || !data.step_type) {
      return {
        ...baseStep,
        referenced_action_id: data.action_id ?? null,
        retry_enabled: data.retry_enabled ?? false,
        retry_max_attempts: data.retry_max_attempts ?? null,
        retry_interval_seconds: data.retry_interval_seconds ?? null,
        retry_backoff_multiplier: data.retry_backoff_multiplier ?? null,
      };
    }

    if (stepType === 'service_call') {
      return {
        ...baseStep,
        integration_type: data.integration_type ?? null,
        operation: data.operation ?? null,
        input_mapping: data.input_mapping ?? null,
        output_mapping: data.output_mapping ?? null,
      };
    }

    if (stepType === 'evaluation') {
      return {
        ...baseStep,
        policy_id: data.policy_id ?? null,
        input_mapping: data.input_mapping ?? null,
      };
    }

    if (stepType === 'gate') {
      return {
        ...baseStep,
        gate_type: data.gate_type ?? null,
        on_timeout: data.on_timeout ?? null,
        context_from: data.context_from ?? null,
        approver_profile_ids: data.approver_profile_ids ?? null,
        timeout: data.timeout ?? null,
      };
    }

    if (stepType === 'http_request') {
      return {
        ...baseStep,
        url: data.url ?? null,
        method: data.method ?? null,
        headers: data.headers ?? null,
        request_timeout: data.request_timeout ?? null,
        input_mapping: data.input_mapping ?? null,
        output_mapping: data.output_mapping ?? null,
      };
    }

    if (stepType === 'schedule_execution') {
      return {
        ...baseStep,
        referenced_action_id: data.action_id ?? null,
        schedule_config: data.schedule_config ?? null,
      };
    }

    // Fallback
    return baseStep;
  });
}

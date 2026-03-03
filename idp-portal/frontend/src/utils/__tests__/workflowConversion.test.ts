/**
 * Tests for workflowConversion utilities — Story 26.5 AC8
 */
import { describe, it, expect } from 'vitest';
import type { Node, Edge } from '@xyflow/react';
import {
  generateStepId,
  START_NODE_ID,
  END_NODE_ID,
  workflowStepsToReactFlow,
  reactFlowToWorkflowSteps,
} from '../workflowConversion';
import type { WorkflowStep } from '../../types/api';

describe('generateStepId', () => {
  it('generates a string ID', () => {
    const id = generateStepId();
    expect(typeof id).toBe('string');
    expect(id.length).toBeGreaterThan(0);
  });

  it('generates unique IDs on successive calls', () => {
    const ids = new Set(Array.from({ length: 10 }, () => generateStepId()));
    expect(ids.size).toBe(10);
  });

  it('falls back when crypto.randomUUID is unavailable', () => {
    const originalRandomUUID = crypto.randomUUID;
    // @ts-expect-error test override
    crypto.randomUUID = undefined;
    const id = generateStepId();
    expect(id).toMatch(/^step-/);
    crypto.randomUUID = originalRandomUUID;
  });
});

describe('constants', () => {
  it('START_NODE_ID is __start__', () => {
    expect(START_NODE_ID).toBe('__start__');
  });

  it('END_NODE_ID is __end__', () => {
    expect(END_NODE_ID).toBe('__end__');
  });
});

describe('workflowStepsToReactFlow', () => {
  const makeStep = (overrides: Partial<WorkflowStep> = {}): WorkflowStep => ({
    order: 1,
    step_id: 'step-1',
    name: 'Step 1',
    referenced_action_id: 10,
    on_success_step_id: null,
    on_error_step_id: null,
    retry_enabled: false,
    retry_max_attempts: null,
    retry_interval_seconds: null,
    retry_backoff_multiplier: null,
    ...overrides,
  });

  it('returns start and end nodes for empty steps', () => {
    const { nodes, edges } = workflowStepsToReactFlow([]);
    expect(nodes).toHaveLength(2);
    expect(nodes[0].id).toBe(START_NODE_ID);
    expect(nodes[1].id).toBe(END_NODE_ID);
    expect(edges).toHaveLength(0);
  });

  it('creates workflow nodes plus Start and End nodes', () => {
    const steps = [makeStep()];
    const { nodes } = workflowStepsToReactFlow(steps);
    expect(nodes).toHaveLength(3); // start + 1 step + end
    expect(nodes[0].id).toBe(START_NODE_ID);
    expect(nodes[1].id).toBe('step-1');
    expect(nodes[2].id).toBe(END_NODE_ID);
  });

  it('auto-connects Start → first step', () => {
    const steps = [makeStep()];
    const { edges } = workflowStepsToReactFlow(steps);
    const startEdge = edges.find((e) => e.source === START_NODE_ID);
    expect(startEdge).toBeDefined();
    expect(startEdge!.target).toBe('step-1');
    expect(startEdge!.sourceHandle).toBe('output');
  });

  it('creates success edges to End node when on_success_step_id is null', () => {
    const steps = [makeStep({ on_success_step_id: null })];
    const { edges } = workflowStepsToReactFlow(steps);
    const endEdge = edges.find(
      (e) => e.source === 'step-1' && e.sourceHandle === 'success' && e.target === END_NODE_ID
    );
    expect(endEdge).toBeDefined();
  });

  it('creates error edges to End node when on_error_step_id is null', () => {
    const steps = [makeStep({ on_error_step_id: null })];
    const { edges } = workflowStepsToReactFlow(steps);
    const endEdge = edges.find(
      (e) => e.source === 'step-1' && e.sourceHandle === 'error' && e.target === END_NODE_ID
    );
    expect(endEdge).toBeDefined();
  });

  it('creates success edges between steps when on_success_step_id is set', () => {
    const steps = [
      makeStep({ step_id: 'step-1', on_success_step_id: 'step-2' }),
      makeStep({ step_id: 'step-2', order: 2, name: 'Step 2' }),
    ];
    const { edges } = workflowStepsToReactFlow(steps);
    const successEdge = edges.find(
      (e) => e.source === 'step-1' && e.sourceHandle === 'success' && e.target === 'step-2'
    );
    expect(successEdge).toBeDefined();
    expect(successEdge!.style).toEqual(expect.objectContaining({ stroke: '#16a34a' }));
  });

  it('creates error edges between steps when on_error_step_id is set', () => {
    const steps = [
      makeStep({ step_id: 'step-1', on_error_step_id: 'step-2' }),
      makeStep({ step_id: 'step-2', order: 2, name: 'Step 2' }),
    ];
    const { edges } = workflowStepsToReactFlow(steps);
    const errorEdge = edges.find(
      (e) => e.source === 'step-1' && e.sourceHandle === 'error' && e.target === 'step-2'
    );
    expect(errorEdge).toBeDefined();
    expect(errorEdge!.style).toEqual(expect.objectContaining({ stroke: '#dc2626' }));
  });

  it('positions nodes in a grid layout', () => {
    const steps = Array.from({ length: 5 }, (_, i) =>
      makeStep({ step_id: `step-${i}`, order: i + 1, name: `Step ${i}` })
    );
    const { nodes } = workflowStepsToReactFlow(steps);
    // First workflow node at index 1 (after start)
    const wfNodes = nodes.filter((n) => n.type === 'workflowStep');
    expect(wfNodes[0].position.x).toBe(0);
    expect(wfNodes[1].position.x).toBe(280);
    expect(wfNodes[4].position.x).toBe(0); // wraps at 4 columns
    expect(wfNodes[4].position.y).toBe(Math.floor(4 / 4) * 200 + 120);
  });

  it('populates on_success_step_name and on_error_step_name in node data', () => {
    const steps = [
      makeStep({ step_id: 'step-1', on_success_step_id: 'step-2', on_error_step_id: 'step-3' }),
      makeStep({ step_id: 'step-2', order: 2, name: 'Success Step' }),
      makeStep({ step_id: 'step-3', order: 3, name: 'Error Step' }),
    ];
    const { nodes } = workflowStepsToReactFlow(steps);
    const step1Data = nodes.find((n) => n.id === 'step-1')!.data;
    expect(step1Data.on_success_step_name).toBe('Success Step');
    expect(step1Data.on_error_step_name).toBe('Error Step');
  });

  it('sets start/end nodes as non-deletable, non-selectable, draggable', () => {
    const { nodes } = workflowStepsToReactFlow([makeStep()]);
    const start = nodes.find((n) => n.id === START_NODE_ID)!;
    const end = nodes.find((n) => n.id === END_NODE_ID)!;
    expect(start.draggable).toBe(true);
    expect(start.selectable).toBe(false);
    expect(start.deletable).toBe(false);
    expect(end.draggable).toBe(true);
    expect(end.selectable).toBe(false);
    expect(end.deletable).toBe(false);
  });
});

describe('workflowStepsToReactFlow — Story 57.13 nouveaux types', () => {
  it('copie step_type dans le node data (service_call)', () => {
    const step: WorkflowStep = {
      order: 1,
      step_id: 'sc-1',
      step_type: 'service_call',
      name: 'Mon service',
      integration_type: 'servicenow',
      operation: 'create_change',
      input_mapping: { param: 'value' },
      output_mapping: { result: '$.number' },
      condition: { environment_in: ['PROD'] },
    };
    const { nodes } = workflowStepsToReactFlow([step]);
    const nodeData = nodes.find((n) => n.id === 'sc-1')!.data;
    expect(nodeData.step_type).toBe('service_call');
    expect(nodeData.integration_type).toBe('servicenow');
    expect(nodeData.operation).toBe('create_change');
    expect(nodeData.output_mapping).toEqual({ result: '$.number' });
  });

  it('copie step_type dans le node data (evaluation)', () => {
    const step: WorkflowStep = {
      order: 1,
      step_id: 'ev-1',
      step_type: 'evaluation',
      name: null,
      policy_id: 42,
    };
    const { nodes } = workflowStepsToReactFlow([step]);
    const nodeData = nodes.find((n) => n.id === 'ev-1')!.data;
    expect(nodeData.step_type).toBe('evaluation');
    expect(nodeData.policy_id).toBe(42);
  });

  it('copie step_type dans le node data (gate)', () => {
    const step: WorkflowStep = {
      order: 1,
      step_id: 'g-1',
      step_type: 'gate',
      name: null,
      gate_type: 'approval',
      on_timeout: 'FAIL',
      timeout: '24h',
    };
    const { nodes } = workflowStepsToReactFlow([step]);
    const nodeData = nodes.find((n) => n.id === 'g-1')!.data;
    expect(nodeData.step_type).toBe('gate');
    expect(nodeData.gate_type).toBe('approval');
    expect(nodeData.timeout).toBe('24h');
  });

  it('copie step_type dans le node data (http_request)', () => {
    const step: WorkflowStep = {
      order: 1,
      step_id: 'http-1',
      step_type: 'http_request',
      name: null,
      url: 'https://api.exemple.com',
      method: 'POST',
      request_timeout: 30,
    };
    const { nodes } = workflowStepsToReactFlow([step]);
    const nodeData = nodes.find((n) => n.id === 'http-1')!.data;
    expect(nodeData.step_type).toBe('http_request');
    expect(nodeData.url).toBe('https://api.exemple.com');
    expect(nodeData.method).toBe('POST');
  });

  it('backward compat: step sans step_type → platform dans node data', () => {
    const step: WorkflowStep = {
      order: 1,
      step_id: 'p-1',
      name: 'Step platform',
      referenced_action_id: 5,
    };
    const { nodes } = workflowStepsToReactFlow([step]);
    const nodeData = nodes.find((n) => n.id === 'p-1')!.data;
    expect(nodeData.step_type).toBe('platform');
  });
});

describe('reactFlowToWorkflowSteps — Story 57.13 round-trips', () => {
  it('round-trip service_call step', () => {
    const step: WorkflowStep = {
      order: 1,
      step_id: 'sc-1',
      step_type: 'service_call',
      name: 'Mon service',
      integration_type: 'servicenow',
      operation: 'create_change',
      input_mapping: { param: 'value' },
      output_mapping: { result: '$.number' },
    };
    const { nodes, edges } = workflowStepsToReactFlow([step]);
    const result = reactFlowToWorkflowSteps(nodes, edges);
    expect(result[0].step_type).toBe('service_call');
    expect(result[0].integration_type).toBe('servicenow');
    expect(result[0].operation).toBe('create_change');
    expect(result[0].output_mapping).toEqual({ result: '$.number' });
    expect(result[0].referenced_action_id).toBeUndefined();
  });

  it('round-trip evaluation step', () => {
    const step: WorkflowStep = {
      order: 1,
      step_id: 'ev-1',
      step_type: 'evaluation',
      name: null,
      policy_id: 99,
    };
    const { nodes, edges } = workflowStepsToReactFlow([step]);
    const result = reactFlowToWorkflowSteps(nodes, edges);
    expect(result[0].step_type).toBe('evaluation');
    expect(result[0].policy_id).toBe(99);
  });

  it('round-trip gate step', () => {
    const step: WorkflowStep = {
      order: 1,
      step_id: 'g-1',
      step_type: 'gate',
      name: null,
      gate_type: 'maintenance_window',
      on_timeout: 'SKIP',
      timeout: '2h',
    };
    const { nodes, edges } = workflowStepsToReactFlow([step]);
    const result = reactFlowToWorkflowSteps(nodes, edges);
    expect(result[0].step_type).toBe('gate');
    expect(result[0].gate_type).toBe('maintenance_window');
    expect(result[0].on_timeout).toBe('SKIP');
    expect(result[0].timeout).toBe('2h');
  });

  it('round-trip http_request step', () => {
    const step: WorkflowStep = {
      order: 1,
      step_id: 'h-1',
      step_type: 'http_request',
      name: null,
      url: 'https://api.test.com/v1',
      method: 'GET',
      headers: { Authorization: 'Bearer token' },
      request_timeout: 10,
    };
    const { nodes, edges } = workflowStepsToReactFlow([step]);
    const result = reactFlowToWorkflowSteps(nodes, edges);
    expect(result[0].step_type).toBe('http_request');
    expect(result[0].url).toBe('https://api.test.com/v1');
    expect(result[0].method).toBe('GET');
    expect(result[0].request_timeout).toBe(10);
  });

  it('round-trip http_request step préserve input_mapping (params URL)', () => {
    const step: WorkflowStep = {
      order: 1,
      step_id: 'h-2',
      step_type: 'http_request',
      name: null,
      url: 'https://api.test.com/search',
      method: 'GET',
      input_mapping: { q: 'query_value', page: '1' },
      output_mapping: { results: '$.items' },
    };
    const { nodes, edges } = workflowStepsToReactFlow([step]);
    const result = reactFlowToWorkflowSteps(nodes, edges);
    expect(result[0].step_type).toBe('http_request');
    expect(result[0].input_mapping).toEqual({ q: 'query_value', page: '1' });
    expect(result[0].output_mapping).toEqual({ results: '$.items' });
  });

  it('backward compat: platform step sans step_type → force platform dans result', () => {
    const nodes: Node[] = [
      { id: START_NODE_ID, type: 'start', position: { x: 0, y: 0 }, data: {} },
      {
        id: 'p-1', type: 'workflowStep', position: { x: 0, y: 120 },
        data: { action_id: 5, name: 'P1', retry_enabled: false, retry_max_attempts: null, retry_interval_seconds: null, retry_backoff_multiplier: null },
      },
      { id: END_NODE_ID, type: 'end', position: { x: 0, y: 300 }, data: {} },
    ];
    const result = reactFlowToWorkflowSteps(nodes, []);
    expect(result[0].step_type).toBe('platform');
    expect(result[0].referenced_action_id).toBe(5);
  });
});

describe('reactFlowToWorkflowSteps', () => {
  it('converts empty arrays to empty steps', () => {
    const result = reactFlowToWorkflowSteps([], []);
    expect(result).toEqual([]);
  });

  it('excludes start and end nodes from conversion', () => {
    const nodes: Node[] = [
      { id: START_NODE_ID, type: 'start', position: { x: 0, y: 0 }, data: {} },
      {
        id: 'step-1', type: 'workflowStep', position: { x: 0, y: 120 },
        data: { action_id: 10, name: 'Test', retry_enabled: false, retry_max_attempts: null, retry_interval_seconds: null, retry_backoff_multiplier: null },
      },
      { id: END_NODE_ID, type: 'end', position: { x: 0, y: 300 }, data: {} },
    ];
    const result = reactFlowToWorkflowSteps(nodes, []);
    expect(result).toHaveLength(1);
    expect(result[0].step_id).toBe('step-1');
  });

  it('maps edges to on_success_step_id and on_error_step_id', () => {
    const nodes: Node[] = [
      { id: START_NODE_ID, type: 'start', position: { x: 0, y: 0 }, data: {} },
      { id: 'step-1', type: 'workflowStep', position: { x: 0, y: 120 }, data: { action_id: 10, name: 'S1', retry_enabled: false, retry_max_attempts: null, retry_interval_seconds: null, retry_backoff_multiplier: null } },
      { id: 'step-2', type: 'workflowStep', position: { x: 280, y: 120 }, data: { action_id: 20, name: 'S2', retry_enabled: false, retry_max_attempts: null, retry_interval_seconds: null, retry_backoff_multiplier: null } },
      { id: END_NODE_ID, type: 'end', position: { x: 0, y: 300 }, data: {} },
    ];
    const edges: Edge[] = [
      { id: 'e1', source: 'step-1', target: 'step-2', sourceHandle: 'success' },
      { id: 'e2', source: 'step-1', target: 'step-2', sourceHandle: 'error' },
    ];
    const result = reactFlowToWorkflowSteps(nodes, edges);
    expect(result[0].on_success_step_id).toBe('step-2');
    expect(result[0].on_error_step_id).toBe('step-2');
  });

  it('sets null for edges pointing to End node', () => {
    const nodes: Node[] = [
      { id: START_NODE_ID, type: 'start', position: { x: 0, y: 0 }, data: {} },
      { id: 'step-1', type: 'workflowStep', position: { x: 0, y: 120 }, data: { action_id: 10, name: 'S1', retry_enabled: false, retry_max_attempts: null, retry_interval_seconds: null, retry_backoff_multiplier: null } },
      { id: END_NODE_ID, type: 'end', position: { x: 0, y: 300 }, data: {} },
    ];
    const edges: Edge[] = [
      { id: 'e1', source: 'step-1', target: END_NODE_ID, sourceHandle: 'success' },
    ];
    const result = reactFlowToWorkflowSteps(nodes, edges);
    expect(result[0].on_success_step_id).toBeNull();
  });

  it('round-trips correctly: steps → reactflow → steps', () => {
    const originalSteps: WorkflowStep[] = [
      { order: 1, step_id: 'step-1', name: 'Step 1', referenced_action_id: 10, on_success_step_id: 'step-2', on_error_step_id: null, retry_enabled: true, retry_max_attempts: 3, retry_interval_seconds: 5, retry_backoff_multiplier: 2 },
      { order: 2, step_id: 'step-2', name: 'Step 2', referenced_action_id: 20, on_success_step_id: null, on_error_step_id: null, retry_enabled: false, retry_max_attempts: null, retry_interval_seconds: null, retry_backoff_multiplier: null },
    ];
    const { nodes, edges } = workflowStepsToReactFlow(originalSteps);
    const roundTripped = reactFlowToWorkflowSteps(nodes, edges);

    expect(roundTripped).toHaveLength(2);
    expect(roundTripped[0].step_id).toBe('step-1');
    expect(roundTripped[0].on_success_step_id).toBe('step-2');
    expect(roundTripped[0].retry_enabled).toBe(true);
    expect(roundTripped[0].retry_max_attempts).toBe(3);
    expect(roundTripped[1].on_success_step_id).toBeNull();
  });
});

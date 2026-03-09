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
import type { WorkflowStepNodeData } from '../../components/admin/WorkflowStepNode';
import { STYLE_TOKENS } from '../../theme/styleTokens';

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
    expect(successEdge!.style).toEqual(expect.objectContaining({ stroke: STYLE_TOKENS.iconSuccess }));
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
    expect(errorEdge!.style).toEqual(expect.objectContaining({ stroke: STYLE_TOKENS.iconError }));
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

  it('maps edges to on_success_step_ids and on_error_step_ids (Story 67.4)', () => {
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
    expect(result[0].on_success_step_ids).toEqual(['step-2']);
    expect(result[0].on_error_step_ids).toEqual(['step-2']);
  });

  it('produces empty on_success_step_ids array for edges pointing to End node (Story 67.4)', () => {
    const nodes: Node[] = [
      { id: START_NODE_ID, type: 'start', position: { x: 0, y: 0 }, data: {} },
      { id: 'step-1', type: 'workflowStep', position: { x: 0, y: 120 }, data: { action_id: 10, name: 'S1', retry_enabled: false, retry_max_attempts: null, retry_interval_seconds: null, retry_backoff_multiplier: null } },
      { id: END_NODE_ID, type: 'end', position: { x: 0, y: 300 }, data: {} },
    ];
    const edges: Edge[] = [
      { id: 'e1', source: 'step-1', target: END_NODE_ID, sourceHandle: 'success' },
    ];
    const result = reactFlowToWorkflowSteps(nodes, edges);
    expect(result[0].on_success_step_ids).toEqual([]);
  });

  it('round-trips correctly: steps → reactflow → steps (Story 67.4)', () => {
    const originalSteps: WorkflowStep[] = [
      { order: 1, step_id: 'step-1', name: 'Step 1', referenced_action_id: 10, on_success_step_id: 'step-2', on_error_step_id: null, retry_enabled: true, retry_max_attempts: 3, retry_interval_seconds: 5, retry_backoff_multiplier: 2 },
      { order: 2, step_id: 'step-2', name: 'Step 2', referenced_action_id: 20, on_success_step_id: null, on_error_step_id: null, retry_enabled: false, retry_max_attempts: null, retry_interval_seconds: null, retry_backoff_multiplier: null },
    ];
    const { nodes, edges } = workflowStepsToReactFlow(originalSteps);
    const roundTripped = reactFlowToWorkflowSteps(nodes, edges);

    expect(roundTripped).toHaveLength(2);
    expect(roundTripped[0].step_id).toBe('step-1');
    // Story 67.4: rétrocompat — on_success_step_id singulier produit un tableau 1 élément
    expect(roundTripped[0].on_success_step_ids).toEqual(['step-2']);
    expect(roundTripped[0].retry_enabled).toBe(true);
    expect(roundTripped[0].retry_max_attempts).toBe(3);
    expect(roundTripped[1].on_success_step_ids).toEqual([]);
  });
});

// Story 57.16: schedule_execution tests
describe('workflowStepsToReactFlow — Story 57.16 schedule_execution', () => {
  it('préserve schedule_config dans le node data', () => {
    const step: WorkflowStep = {
      order: 1,
      step_id: 'sched-1',
      step_type: 'schedule_execution',
      name: 'Planifier',
      referenced_action_id: 56,
      schedule_config: {
        schedule_source: 'parameter',
        schedule_parameter_name: 'maintenance_scheduled_at',
        inherit_parameters: true,
        inherit_targets: true,
        parameter_mapping: { snapshot_id: '$.steps.prepare.output.snapshot_id' },
      },
    };
    const { nodes } = workflowStepsToReactFlow([step]);
    const nodeData = nodes.find((n) => n.id === 'sched-1')!.data;
    expect(nodeData.step_type).toBe('schedule_execution');
    expect(nodeData.schedule_config).toEqual(step.schedule_config);
    expect(nodeData.action_id).toBe(56);
  });

  it('schedule_config null → null dans node data', () => {
    const step: WorkflowStep = {
      order: 1,
      step_id: 'sched-2',
      step_type: 'schedule_execution',
      name: null,
      schedule_config: null,
    };
    const { nodes } = workflowStepsToReactFlow([step]);
    const nodeData = nodes.find((n) => n.id === 'sched-2')!.data;
    expect(nodeData.schedule_config).toBeNull();
  });
});

describe('reactFlowToWorkflowSteps — Story 57.16 round-trip schedule_execution', () => {
  it('round-trip préserve schedule_config pour schedule_execution step', () => {
    const step: WorkflowStep = {
      order: 1,
      step_id: 'sched-1',
      step_type: 'schedule_execution',
      name: 'Planifier l\'application',
      referenced_action_id: 56,
      schedule_config: {
        schedule_source: 'parameter',
        schedule_parameter_name: 'maintenance_scheduled_at',
        inherit_parameters: true,
        inherit_targets: true,
      },
    };
    const { nodes, edges } = workflowStepsToReactFlow([step]);
    const result = reactFlowToWorkflowSteps(nodes, edges);
    expect(result[0].step_type).toBe('schedule_execution');
    expect(result[0].referenced_action_id).toBe(56);
    expect(result[0].schedule_config).toEqual(step.schedule_config);
  });

  it('round-trip schedule_execution avec fixed_offset', () => {
    const step: WorkflowStep = {
      order: 1,
      step_id: 'sched-2',
      step_type: 'schedule_execution',
      name: null,
      referenced_action_id: 10,
      schedule_config: {
        schedule_source: 'fixed_offset',
        fixed_offset: '+3d',
        inherit_parameters: false,
        inherit_targets: false,
      },
    };
    const { nodes, edges } = workflowStepsToReactFlow([step]);
    const result = reactFlowToWorkflowSteps(nodes, edges);
    expect(result[0].schedule_config?.schedule_source).toBe('fixed_offset');
    expect(result[0].schedule_config?.fixed_offset).toBe('+3d');
  });

  it('round-trip schedule_execution avec recurring pattern', () => {
    const step: WorkflowStep = {
      order: 1,
      step_id: 'sched-3',
      step_type: 'schedule_execution',
      name: null,
      referenced_action_id: 10,
      schedule_config: {
        schedule_source: 'recurring',
        recurring_pattern: { pattern_type: 'daily', pattern_config: {} },
      },
    };
    const { nodes, edges } = workflowStepsToReactFlow([step]);
    const result = reactFlowToWorkflowSteps(nodes, edges);
    expect(result[0].schedule_config?.schedule_source).toBe('recurring');
    expect(result[0].schedule_config?.recurring_pattern?.pattern_type).toBe('daily');
  });

  it('round-trip schedule_execution avec parameter_mapping complet', () => {
    const step: WorkflowStep = {
      order: 1,
      step_id: 'sched-4',
      step_type: 'schedule_execution',
      name: 'Planifier l\'application',
      referenced_action_id: 56,
      schedule_config: {
        schedule_source: 'parameter',
        schedule_parameter_name: 'maintenance_scheduled_at',
        inherit_parameters: true,
        inherit_targets: true,
        parameter_mapping: {
          snapshot_id: '$.steps.prepare.output.snapshot_id',
          env: 'PROD',
        },
      },
    };
    const { nodes, edges } = workflowStepsToReactFlow([step]);
    const result = reactFlowToWorkflowSteps(nodes, edges);
    expect(result[0].schedule_config?.parameter_mapping).toEqual({
      snapshot_id: '$.steps.prepare.output.snapshot_id',
      env: 'PROD',
    });
    expect(result[0].schedule_config?.inherit_parameters).toBe(true);
    expect(result[0].schedule_config?.inherit_targets).toBe(true);
    expect(result[0].referenced_action_id).toBe(56);
  });
});

// ── Story 65.4 — parallel_group ────────────────────────────────────────────

describe('workflowStepsToReactFlow — parallel_group', () => {
  it('crée un nœud parallel_group avec les champs dans data (AC #2)', () => {
    const steps: WorkflowStep[] = [
      {
        order: 1,
        step_id: 'pg-1',
        step_type: 'parallel_group',
        name: 'Backups parallèles',
        parallel_steps: ['bk-db', 'bk-cfg'],
        on_all_success_step_id: 'apply-patch',
        on_any_error_step_id: 'rollback',
      },
      { order: 2, step_id: 'bk-db', step_type: 'platform', name: 'Backup DB', referenced_action_id: 10 },
      { order: 3, step_id: 'bk-cfg', step_type: 'platform', name: 'Backup Config', referenced_action_id: 11 },
      { order: 4, step_id: 'apply-patch', step_type: 'platform', name: 'Patch', referenced_action_id: 12 },
      { order: 5, step_id: 'rollback', step_type: 'platform', name: 'Rollback', referenced_action_id: 13 },
    ];
    const { nodes } = workflowStepsToReactFlow(steps);

    const pgNode = nodes.find((n) => n.id === 'pg-1');
    expect(pgNode).toBeDefined();
    const data = pgNode!.data as unknown as WorkflowStepNodeData;
    expect(data.step_type).toBe('parallel_group');
    expect(data.parallel_steps).toEqual(['bk-db', 'bk-cfg']);
    expect(data.on_all_success_step_id).toBe('apply-patch');
    expect(data.on_any_error_step_id).toBe('rollback');
  });

  it('crée edge success vers on_all_success_step_id et error vers on_any_error_step_id (AC #2)', () => {
    const steps: WorkflowStep[] = [
      {
        order: 1, step_id: 'pg-1', step_type: 'parallel_group', name: 'PG',
        parallel_steps: ['s1', 's2'], on_all_success_step_id: 'next', on_any_error_step_id: null,
      },
      { order: 2, step_id: 's1', step_type: 'platform', name: 'S1', referenced_action_id: 1 },
      { order: 3, step_id: 's2', step_type: 'platform', name: 'S2', referenced_action_id: 2 },
      { order: 4, step_id: 'next', step_type: 'platform', name: 'Next', referenced_action_id: 3 },
    ];
    const { edges } = workflowStepsToReactFlow(steps);

    const successEdge = edges.find((e) => e.source === 'pg-1' && e.sourceHandle === 'success');
    expect(successEdge?.target).toBe('next');

    const errorEdge = edges.find((e) => e.source === 'pg-1' && e.sourceHandle === 'error');
    expect(errorEdge?.target).toBe(END_NODE_ID); // null → END_NODE_ID
  });
});

describe('reactFlowToWorkflowSteps — parallel_group', () => {
  it('produit un WorkflowStep parallel_group sans on_success_step_id/on_error_step_id (AC #3)', () => {
    const nodes: Node[] = [
      {
        id: 'pg-1', type: 'workflowStep', position: { x: 0, y: 0 },
        data: {
          step_type: 'parallel_group', name: 'PG',
          parallel_steps: ['s1', 's2'],
          on_all_success_step_id: null, on_any_error_step_id: null,
        },
      },
    ];
    const edges: Edge[] = [];
    const result = reactFlowToWorkflowSteps(nodes, edges);

    expect(result).toHaveLength(1);
    expect(result[0].step_type).toBe('parallel_group');
    expect(result[0].parallel_steps).toEqual(['s1', 's2']);
    expect(result[0].on_all_success_step_id).toBeNull();
    expect(result[0].on_any_error_step_id).toBeNull();
    expect(result[0]).not.toHaveProperty('on_success_step_id');
    expect(result[0]).not.toHaveProperty('on_error_step_id');
  });
});

describe('round-trip parallel_group (AC #8)', () => {
  it('WorkflowStep[] → reactFlow → WorkflowStep[] produit un résultat équivalent', () => {
    const originalSteps: WorkflowStep[] = [
      {
        order: 1, step_id: 'pg-1', step_type: 'parallel_group', name: 'PG',
        parallel_steps: ['s1', 's2'], on_all_success_step_id: 's3', on_any_error_step_id: null,
      },
      { order: 2, step_id: 's1', step_type: 'platform', name: 'S1', referenced_action_id: 1 },
      { order: 3, step_id: 's2', step_type: 'platform', name: 'S2', referenced_action_id: 2 },
      { order: 4, step_id: 's3', step_type: 'platform', name: 'S3', referenced_action_id: 3 },
    ];
    const { nodes, edges } = workflowStepsToReactFlow(originalSteps);
    const reconstructed = reactFlowToWorkflowSteps(nodes, edges);

    const pgStep = reconstructed.find((s) => s.step_id === 'pg-1');
    expect(pgStep?.step_type).toBe('parallel_group');
    expect(pgStep?.parallel_steps).toEqual(['s1', 's2']);
    expect(pgStep?.on_all_success_step_id).toBe('s3');
    expect(pgStep?.on_any_error_step_id).toBeNull();
    expect(pgStep).not.toHaveProperty('on_success_step_id');
    expect(pgStep).not.toHaveProperty('on_error_step_id');
  });
});

// ── Story 67.4 — multi-connexions et join_policy ────────────────────────────

describe('Story 67.4 — reactFlowToWorkflowSteps multi-connexions', () => {
  it('6.1 — produit on_success_step_ids array quand 2 success edges existent', () => {
    const nodes: Node[] = [
      { id: START_NODE_ID, type: 'start', position: { x: 0, y: 0 }, data: {} },
      { id: 'stepA', type: 'workflowStep', position: { x: 0, y: 120 }, data: { step_type: 'platform', name: 'A', retry_enabled: false, retry_max_attempts: null, retry_interval_seconds: null, retry_backoff_multiplier: null } },
      { id: END_NODE_ID, type: 'end', position: { x: 0, y: 400 }, data: {} },
    ];
    const edges: Edge[] = [
      { id: 'stepA_success_stepB', source: 'stepA', target: 'stepB', sourceHandle: 'success', targetHandle: 'input' },
      { id: 'stepA_success_stepC', source: 'stepA', target: 'stepC', sourceHandle: 'success', targetHandle: 'input' },
    ];
    const steps = reactFlowToWorkflowSteps(nodes, edges);
    expect(steps[0].on_success_step_ids).toEqual(['stepB', 'stepC']);
  });

  it('6.2 — rétrocompat singulier : on_success_step_id → workflowStepsToReactFlow crée 1 edge', () => {
    const steps: WorkflowStep[] = [
      { order: 1, step_id: 'stepA', name: null, step_type: 'platform', on_success_step_id: 'stepB' },
    ];
    const { edges } = workflowStepsToReactFlow(steps);
    const successEdges = edges.filter(e => e.source === 'stepA' && e.sourceHandle === 'success' && e.target !== END_NODE_ID);
    expect(successEdges).toHaveLength(1);
    expect(successEdges[0].target).toBe('stepB');
  });

  it('6.3 — round-trip multi-connexion + join_policy', () => {
    const input: WorkflowStep[] = [
      { order: 1, step_id: 'stepA', name: 'A', step_type: 'platform', on_success_step_ids: ['stepB', 'stepC'] },
      { order: 2, step_id: 'stepB', name: 'B', step_type: 'platform', on_success_step_ids: ['stepD'] },
      { order: 3, step_id: 'stepC', name: 'C', step_type: 'platform', on_success_step_ids: ['stepD'] },
      { order: 4, step_id: 'stepD', name: 'D', step_type: 'platform', join_policy: 'one_success', on_success_step_ids: [] },
    ];
    const { nodes, edges } = workflowStepsToReactFlow(input);
    const output = reactFlowToWorkflowSteps(nodes, edges);
    // stepA : fan-out vers stepB et stepC
    expect(output[0].on_success_step_ids).toEqual(['stepB', 'stepC']);
    // stepB et stepC : convergent vers stepD
    expect(output[1].on_success_step_ids).toEqual(['stepD']);
    expect(output[2].on_success_step_ids).toEqual(['stepD']);
    // stepD : join_policy préservé, aucune cible success (fin de workflow)
    expect(output[3].join_policy).toBe('one_success');
    expect(output[3].on_success_step_ids).toEqual([]);
  });

  it('6.5 — join_policy null est absent du résultat de reactFlowToWorkflowSteps', () => {
    const nodes = [
      { id: START_NODE_ID, type: 'start', position: { x: 0, y: 0 }, data: {} },
      { id: 'stepA', type: 'workflowStep', position: { x: 0, y: 120 },
        data: { step_type: 'platform', name: 'A', join_policy: null,
          retry_enabled: false, retry_max_attempts: null, retry_interval_seconds: null, retry_backoff_multiplier: null } },
      { id: END_NODE_ID, type: 'end', position: { x: 0, y: 300 }, data: {} },
    ];
    const result = reactFlowToWorkflowSteps(nodes, []);
    expect(result[0]).not.toHaveProperty('join_policy');
  });

  it('6.4 — workflowStepsToReactFlow avec on_success_step_ids: 2 targets → 2 edges', () => {
    const steps: WorkflowStep[] = [
      { order: 1, step_id: 'stepA', name: 'A', step_type: 'platform', on_success_step_ids: ['stepB', 'stepC'] },
    ];
    const { edges } = workflowStepsToReactFlow(steps);
    const successEdges = edges.filter(e => e.source === 'stepA' && e.sourceHandle === 'success' && e.target !== END_NODE_ID);
    expect(successEdges).toHaveLength(2);
    expect(successEdges.map(e => e.target)).toContain('stepB');
    expect(successEdges.map(e => e.target)).toContain('stepC');
  });
});

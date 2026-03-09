/**
 * Tests for workflowValidation utilities — Story 26.5 AC8; Story 57.13 AC8
 */
import { describe, it, expect } from 'vitest';
import type { Node, Edge } from '@xyflow/react';
import { validateWorkflowGraph } from '../workflowValidation';
import { START_NODE_ID, END_NODE_ID } from '../workflowConversion';
import type { WorkflowStepNodeData } from '../../components/admin/WorkflowStepNode';

const makeNodeWithData = (id: string, data: Partial<WorkflowStepNodeData> = {}): Node => ({
  id,
  type: 'workflowStep',
  position: { x: 0, y: 0 },
  data,
});

const makeNode = (id: string): Node => ({
  id,
  type: 'workflowStep',
  position: { x: 0, y: 0 },
  data: {},
});

const makeEdge = (source: string, target: string, sourceHandle: string = 'success'): Edge => ({
  id: `${source}_${sourceHandle}_${target}`,
  source,
  target,
  sourceHandle,
});

const startNode: Node = { id: START_NODE_ID, type: 'start', position: { x: 0, y: 0 }, data: {} };
const endNode: Node = { id: END_NODE_ID, type: 'end', position: { x: 0, y: 300 }, data: {} };

describe('validateWorkflowGraph', () => {
  it('returns error for empty graph (no workflow nodes)', () => {
    const result = validateWorkflowGraph([startNode, endNode], []);
    expect(result.valid).toBe(false);
    expect(result.errors).toHaveLength(1);
    expect(result.errors[0].message).toContain('Au moins une étape');
  });

  it('returns valid for a single connected node', () => {
    const nodes = [startNode, makeNode('step-1'), endNode];
    const edges = [
      makeEdge('step-1', END_NODE_ID, 'success'),
      makeEdge('step-1', END_NODE_ID, 'error'),
    ];
    const result = validateWorkflowGraph(nodes, edges);
    expect(result.valid).toBe(true);
    expect(result.errors.filter((e) => e.type === 'error')).toHaveLength(0);
  });

  it('detects node without output connections as warning', () => {
    const nodes = [startNode, makeNode('step-1'), endNode];
    const edges: Edge[] = []; // no edges at all
    const result = validateWorkflowGraph(nodes, edges);
    // Should be valid (warnings only, no errors — single node so no orphan detection)
    expect(result.valid).toBe(true);
    const warnings = result.errors.filter((e) => e.type === 'warning');
    expect(warnings.length).toBeGreaterThanOrEqual(1);
    expect(warnings[0].message).toContain('Pas de chemin de sortie');
  });

  it('detects orphan nodes (not reachable from start)', () => {
    const nodes = [startNode, makeNode('step-1'), makeNode('step-2'), endNode];
    // START → step-1 → End, but step-2 has no incoming edges (orphan)
    const edges = [
      makeEdge(START_NODE_ID, 'step-1', 'output'), // START connects to step-1
      makeEdge('step-1', END_NODE_ID, 'success'),
    ];
    const result = validateWorkflowGraph(nodes, edges);
    expect(result.valid).toBe(false);
    const orphanErrors = result.errors.filter(
      (e) => e.type === 'error' && e.message.includes('Non atteignable')
    );
    expect(orphanErrors).toHaveLength(1); // Only orphan step-2
    expect(orphanErrors[0].nodeId).toBe('step-2');
  });

  it('detects infinite loops (cycles)', () => {
    const nodes = [startNode, makeNode('step-1'), makeNode('step-2'), endNode];
    const edges = [
      makeEdge('step-1', 'step-2', 'success'),
      makeEdge('step-2', 'step-1', 'success'), // cycle
    ];
    const result = validateWorkflowGraph(nodes, edges);
    expect(result.valid).toBe(false);
    const loopErrors = result.errors.filter(
      (e) => e.type === 'error' && e.message.includes('Boucle infinie')
    );
    expect(loopErrors.length).toBeGreaterThanOrEqual(1);
  });

  it('detects self-referencing cycle', () => {
    const nodes = [startNode, makeNode('step-1'), endNode];
    const edges = [
      makeEdge('step-1', 'step-1', 'success'), // self-loop
    ];
    const result = validateWorkflowGraph(nodes, edges);
    expect(result.valid).toBe(false);
    const loopErrors = result.errors.filter(
      (e) => e.type === 'error' && e.message.includes('Boucle infinie')
    );
    expect(loopErrors.length).toBeGreaterThanOrEqual(1);
  });

  it('validates complex valid graph without false positives', () => {
    // START → A → B (success), A → C (error), B → End, C → End
    const nodes = [startNode, makeNode('A'), makeNode('B'), makeNode('C'), endNode];
    const edges = [
      makeEdge(START_NODE_ID, 'A', 'output'), // START connects to A
      makeEdge('A', 'B', 'success'),
      makeEdge('A', 'C', 'error'),
      makeEdge('B', END_NODE_ID, 'success'),
      makeEdge('B', END_NODE_ID, 'error'),
      makeEdge('C', END_NODE_ID, 'success'),
      makeEdge('C', END_NODE_ID, 'error'),
    ];
    const result = validateWorkflowGraph(nodes, edges);
    expect(result.valid).toBe(true);
    expect(result.errors.filter((e) => e.type === 'error')).toHaveLength(0);
  });

  it('ignores start and end visual nodes in validation', () => {
    const nodes = [startNode, makeNode('step-1'), endNode];
    const edges = [
      makeEdge(START_NODE_ID, 'step-1', 'output'),
      makeEdge('step-1', END_NODE_ID, 'success'),
    ];
    const result = validateWorkflowGraph(nodes, edges);
    // Start/end should not appear in errors
    const startEndErrors = result.errors.filter(
      (e) => e.nodeId === START_NODE_ID || e.nodeId === END_NODE_ID
    );
    expect(startEndErrors).toHaveLength(0);
  });
});

describe('validateWorkflowGraph — Story 57.13 AC8 — validation per step_type', () => {
  const startNode: Node = { id: START_NODE_ID, type: 'start', position: { x: 0, y: 0 }, data: {} };
  const endNode: Node = { id: END_NODE_ID, type: 'end', position: { x: 0, y: 300 }, data: {} };
  const edgesForNode = (id: string): Edge[] => [
    makeEdge(START_NODE_ID, id, 'output'),
    makeEdge(id, END_NODE_ID, 'success'),
    makeEdge(id, END_NODE_ID, 'error'),
  ];

  it('platform sans action_id → erreur', () => {
    const node = makeNodeWithData('p-1', { step_type: 'platform' });
    const result = validateWorkflowGraph([startNode, node, endNode], edgesForNode('p-1'));
    const errors = result.errors.filter((e) => e.nodeId === 'p-1' && e.type === 'error');
    expect(errors.some((e) => e.message.includes('Action requise'))).toBe(true);
  });

  it('platform avec action_id → pas d\'erreur de type', () => {
    const node = makeNodeWithData('p-1', { step_type: 'platform', action_id: 10 });
    const result = validateWorkflowGraph([startNode, node, endNode], edgesForNode('p-1'));
    const typeErrors = result.errors.filter((e) => e.nodeId === 'p-1' && e.type === 'error');
    expect(typeErrors).toHaveLength(0);
  });

  it('service_call sans integration_type → erreur', () => {
    const node = makeNodeWithData('sc-1', { step_type: 'service_call', operation: 'create_change' });
    const result = validateWorkflowGraph([startNode, node, endNode], edgesForNode('sc-1'));
    const errors = result.errors.filter((e) => e.nodeId === 'sc-1' && e.type === 'error');
    expect(errors.some((e) => e.message.includes("intégration"))).toBe(true);
  });

  it('service_call sans operation → erreur', () => {
    const node = makeNodeWithData('sc-1', { step_type: 'service_call', integration_type: 'servicenow' });
    const result = validateWorkflowGraph([startNode, node, endNode], edgesForNode('sc-1'));
    const errors = result.errors.filter((e) => e.nodeId === 'sc-1' && e.type === 'error');
    expect(errors.some((e) => e.message.includes('Opération'))).toBe(true);
  });

  it('service_call complet → pas d\'erreur de type', () => {
    const node = makeNodeWithData('sc-1', {
      step_type: 'service_call',
      integration_type: 'servicenow',
      operation: 'create_change',
    });
    const result = validateWorkflowGraph([startNode, node, endNode], edgesForNode('sc-1'));
    const typeErrors = result.errors.filter((e) => e.nodeId === 'sc-1' && e.type === 'error');
    expect(typeErrors).toHaveLength(0);
  });

  it('evaluation sans policy_id → erreur', () => {
    const node = makeNodeWithData('ev-1', { step_type: 'evaluation' });
    const result = validateWorkflowGraph([startNode, node, endNode], edgesForNode('ev-1'));
    const errors = result.errors.filter((e) => e.nodeId === 'ev-1' && e.type === 'error');
    expect(errors.some((e) => e.message.includes('Politique'))).toBe(true);
  });

  it('evaluation avec policy_id → pas d\'erreur de type', () => {
    const node = makeNodeWithData('ev-1', { step_type: 'evaluation', policy_id: 5 });
    const result = validateWorkflowGraph([startNode, node, endNode], edgesForNode('ev-1'));
    const typeErrors = result.errors.filter((e) => e.nodeId === 'ev-1' && e.type === 'error');
    expect(typeErrors).toHaveLength(0);
  });

  it('gate sans gate_type → erreur', () => {
    const node = makeNodeWithData('g-1', { step_type: 'gate' });
    const result = validateWorkflowGraph([startNode, node, endNode], edgesForNode('g-1'));
    const errors = result.errors.filter((e) => e.nodeId === 'g-1' && e.type === 'error');
    expect(errors.some((e) => e.message.includes('gate'))).toBe(true);
  });

  it('gate avec gate_type → pas d\'erreur de type', () => {
    const node = makeNodeWithData('g-1', { step_type: 'gate', gate_type: 'approval' });
    const result = validateWorkflowGraph([startNode, node, endNode], edgesForNode('g-1'));
    const typeErrors = result.errors.filter((e) => e.nodeId === 'g-1' && e.type === 'error');
    expect(typeErrors).toHaveLength(0);
  });

  it('http_request sans url → erreur', () => {
    const node = makeNodeWithData('h-1', { step_type: 'http_request', method: 'GET' });
    const result = validateWorkflowGraph([startNode, node, endNode], edgesForNode('h-1'));
    const errors = result.errors.filter((e) => e.nodeId === 'h-1' && e.type === 'error');
    expect(errors.some((e) => e.message.includes('URL'))).toBe(true);
  });

  it('http_request sans method → erreur', () => {
    const node = makeNodeWithData('h-1', { step_type: 'http_request', url: 'https://api.test.com' });
    const result = validateWorkflowGraph([startNode, node, endNode], edgesForNode('h-1'));
    const errors = result.errors.filter((e) => e.nodeId === 'h-1' && e.type === 'error');
    expect(errors.some((e) => e.message.includes('Méthode'))).toBe(true);
  });

  it('http_request complet → pas d\'erreur de type', () => {
    const node = makeNodeWithData('h-1', {
      step_type: 'http_request',
      url: 'https://api.test.com',
      method: 'POST',
    });
    const result = validateWorkflowGraph([startNode, node, endNode], edgesForNode('h-1'));
    const typeErrors = result.errors.filter((e) => e.nodeId === 'h-1' && e.type === 'error');
    expect(typeErrors).toHaveLength(0);
  });

  // Story 57.16: schedule_execution validation
  it('schedule_execution sans action_id → erreur', () => {
    const node = makeNodeWithData('s-1', {
      step_type: 'schedule_execution',
      schedule_config: { schedule_source: 'parameter', schedule_parameter_name: 'date' },
    });
    const result = validateWorkflowGraph([startNode, node, endNode], edgesForNode('s-1'));
    const errors = result.errors.filter((e) => e.nodeId === 's-1' && e.type === 'error');
    expect(errors.some((e) => e.message.includes('Action cible'))).toBe(true);
  });

  it('schedule_execution sans schedule_config → erreur', () => {
    const node = makeNodeWithData('s-1', {
      step_type: 'schedule_execution',
      action_id: 56,
    });
    const result = validateWorkflowGraph([startNode, node, endNode], edgesForNode('s-1'));
    const errors = result.errors.filter((e) => e.nodeId === 's-1' && e.type === 'error');
    expect(errors.some((e) => e.message.includes('Configuration de planification'))).toBe(true);
  });

  it('schedule_execution source=parameter sans schedule_parameter_name → erreur', () => {
    const node = makeNodeWithData('s-1', {
      step_type: 'schedule_execution',
      action_id: 56,
      schedule_config: { schedule_source: 'parameter' },
    });
    const result = validateWorkflowGraph([startNode, node, endNode], edgesForNode('s-1'));
    const errors = result.errors.filter((e) => e.nodeId === 's-1' && e.type === 'error');
    expect(errors.some((e) => e.message.includes('schedule_parameter_name'))).toBe(true);
  });

  it('schedule_execution source=fixed_offset sans fixed_offset → erreur', () => {
    const node = makeNodeWithData('s-1', {
      step_type: 'schedule_execution',
      action_id: 56,
      schedule_config: { schedule_source: 'fixed_offset' },
    });
    const result = validateWorkflowGraph([startNode, node, endNode], edgesForNode('s-1'));
    const errors = result.errors.filter((e) => e.nodeId === 's-1' && e.type === 'error');
    expect(errors.some((e) => e.message.includes('Offset fixe'))).toBe(true);
  });

  it('schedule_execution source=recurring sans pattern_type → erreur', () => {
    const node = makeNodeWithData('s-1', {
      step_type: 'schedule_execution',
      action_id: 56,
      schedule_config: { schedule_source: 'recurring' },
    });
    const result = validateWorkflowGraph([startNode, node, endNode], edgesForNode('s-1'));
    const errors = result.errors.filter((e) => e.nodeId === 's-1' && e.type === 'error');
    expect(errors.some((e) => e.message.includes('pattern récurrent'))).toBe(true);
  });

  it('schedule_execution complet avec parameter source → pas d\'erreur de type', () => {
    const node = makeNodeWithData('s-1', {
      step_type: 'schedule_execution',
      action_id: 56,
      schedule_config: {
        schedule_source: 'parameter',
        schedule_parameter_name: 'maintenance_at',
      },
    });
    const result = validateWorkflowGraph([startNode, node, endNode], edgesForNode('s-1'));
    const typeErrors = result.errors.filter((e) => e.nodeId === 's-1' && e.type === 'error');
    expect(typeErrors).toHaveLength(0);
  });

  it('schedule_execution complet avec fixed_offset source → pas d\'erreur de type', () => {
    const node = makeNodeWithData('s-1', {
      step_type: 'schedule_execution',
      action_id: 56,
      schedule_config: {
        schedule_source: 'fixed_offset',
        fixed_offset: '+3d',
      },
    });
    const result = validateWorkflowGraph([startNode, node, endNode], edgesForNode('s-1'));
    const typeErrors = result.errors.filter((e) => e.nodeId === 's-1' && e.type === 'error');
    expect(typeErrors).toHaveLength(0);
  });

  // Story 65.4: parallel_group validation (AC #7)
  it('error si parallel_group sans parallel_steps', () => {
    const node = makeNodeWithData('pg-1', { step_type: 'parallel_group' });
    const result = validateWorkflowGraph(
      [startNode, node, endNode],
      [makeEdge('pg-1', END_NODE_ID, 'success'), makeEdge('pg-1', END_NODE_ID, 'error')],
    );
    const typeErrors = result.errors.filter((e) => e.nodeId === 'pg-1' && e.type === 'error');
    expect(typeErrors.length).toBeGreaterThan(0);
    expect(typeErrors[0].message).toContain('parallel_steps');
  });

  it('error si parallel_group avec parallel_steps < 2', () => {
    const node = makeNodeWithData('pg-1', { step_type: 'parallel_group', parallel_steps: ['s1'] });
    const result = validateWorkflowGraph(
      [startNode, node, endNode],
      [makeEdge('pg-1', END_NODE_ID, 'success'), makeEdge('pg-1', END_NODE_ID, 'error')],
    );
    const typeErrors = result.errors.filter((e) => e.nodeId === 'pg-1' && e.type === 'error');
    expect(typeErrors.length).toBeGreaterThan(0);
    expect(typeErrors[0].message).toContain('parallel_steps');
  });

  it('valide sans erreur si parallel_group avec parallel_steps ≥ 2', () => {
    const s1 = makeNodeWithData('s1', { step_type: 'platform' });
    const s2 = makeNodeWithData('s2', { step_type: 'platform' });
    const node = makeNodeWithData('pg-1', { step_type: 'parallel_group', parallel_steps: ['s1', 's2'] });
    const result = validateWorkflowGraph(
      [startNode, node, s1, s2, endNode],
      [
        makeEdge(START_NODE_ID, 'pg-1', 'output'),
        makeEdge('pg-1', END_NODE_ID, 'success'),
        makeEdge('pg-1', END_NODE_ID, 'error'),
        makeEdge('s1', END_NODE_ID, 'success'),
        makeEdge('s2', END_NODE_ID, 'success'),
      ],
    );
    const typeErrors = result.errors.filter((e) => e.nodeId === 'pg-1' && e.type === 'error');
    expect(typeErrors).toHaveLength(0);
  });

  it('error si parallel_steps référence un membre inexistant', () => {
    const node = makeNodeWithData('pg-1', { step_type: 'parallel_group', parallel_steps: ['s1', 's2'] });
    const result = validateWorkflowGraph(
      [startNode, node, endNode],
      [makeEdge('pg-1', END_NODE_ID, 'success'), makeEdge('pg-1', END_NODE_ID, 'error')],
    );
    const typeErrors = result.errors.filter((e) => e.nodeId === 'pg-1' && e.type === 'error');
    expect(typeErrors.length).toBeGreaterThan(0);
    expect(typeErrors.some((e) => e.message.includes('n\'existe pas'))).toBe(true);
  });
});

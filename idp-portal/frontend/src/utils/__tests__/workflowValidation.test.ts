/**
 * Tests for workflowValidation utilities — Story 26.5 AC8
 */
import { describe, it, expect } from 'vitest';
import type { Node, Edge } from '@xyflow/react';
import { validateWorkflowGraph } from '../workflowValidation';
import { START_NODE_ID, END_NODE_ID } from '../workflowConversion';

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

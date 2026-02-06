/**
 * WorkflowBuilderCanvas tests (Story 16.5, Tasks 8.1-8.4; Story 16.7; Story 16.8).
 *
 * Tests:
 * - Unit: WorkflowStep[] ↔ React Flow conversion (with start/end nodes)
 * - Unit: Workflow graph validation (orphans, cycles, missing outputs)
 * - Integration: Component rendering, drag-and-drop, connections, deletion
 * - Accessibility: ARIA labels, keyboard navigation
 * - Story 16.7: Start/End nodes, custom edges, validation report, save blocking
 * - Story 16.8: Export/Import buttons, dropdown menu, file import dialog
 */

import React from 'react';
import { describe, it, expect, vi, beforeAll } from 'vitest';
import { render, screen, waitFor, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { WorkflowStep } from '../../types/api';
import type { Node, Edge } from '@xyflow/react';
import {
  workflowStepsToReactFlow,
  reactFlowToWorkflowSteps,
  validateWorkflowGraph,
  START_NODE_ID,
  END_NODE_ID,
} from './WorkflowBuilderCanvas';

// Mock admin service
vi.mock('../../services/admin_service', () => ({
  getEligibleActionsForWorkflow: vi.fn().mockResolvedValue([
    { id: 100, name: 'Create PDB', engine: 'Oracle', status: 'published', created_at: '', execution_count: 0 },
    { id: 101, name: 'Apply Patch', engine: 'SQL Server', status: 'published', created_at: '', execution_count: 0 },
    { id: 102, name: 'Backup DB', engine: 'Oracle', status: 'published', created_at: '', execution_count: 0 },
  ]),
}));

// ── Unit Tests: Conversion Functions ───────────────────────────────────────

describe('workflowStepsToReactFlow', () => {
  it('converts empty steps to start+end nodes only', () => {
    const result = workflowStepsToReactFlow([]);
    // Start + End nodes are always present
    expect(result.nodes).toHaveLength(2);
    expect(result.nodes[0].id).toBe(START_NODE_ID);
    expect(result.nodes[1].id).toBe(END_NODE_ID);
    expect(result.edges).toHaveLength(0); // no workflow edges
  });

  it('converts steps to nodes with correct data (plus start/end)', () => {
    const steps: WorkflowStep[] = [
      {
        order: 1,
        step_id: 'step-a',
        name: 'Create PDB',
        referenced_action_id: 100,
        on_success_step_id: null,
        on_error_step_id: null,
        retry_enabled: true,
        retry_max_attempts: 3,
        retry_interval_seconds: 60,
        retry_backoff_multiplier: 2.0,
      },
    ];

    const { nodes, edges } = workflowStepsToReactFlow(steps);

    // Start + 1 workflow node + End = 3
    expect(nodes).toHaveLength(3);
    // Workflow node is at index 1 (between start and end)
    const workflowNode = nodes[1];
    expect(workflowNode.id).toBe('step-a');
    expect(workflowNode.type).toBe('workflowStep');
    expect((workflowNode.data as Record<string, unknown>).action_id).toBe(100);
    expect((workflowNode.data as Record<string, unknown>).retry_enabled).toBe(true);
    expect((workflowNode.data as Record<string, unknown>).retry_max_attempts).toBe(3);
    // Should have start→first edge and first→end edge (since no outputs)
    expect(edges.some((e) => e.source === START_NODE_ID && e.target === 'step-a')).toBe(true);
    expect(edges.some((e) => e.source === 'step-a' && e.target === END_NODE_ID)).toBe(true);
  });

  it('generates fallback step_id when missing', () => {
    const steps: WorkflowStep[] = [
      { order: 1, name: 'Step 1', referenced_action_id: 100 },
    ];

    const { nodes } = workflowStepsToReactFlow(steps);
    // Workflow node is at index 1
    expect(nodes[1].id).toBe('step-0');
  });

  it('creates success edges with green style and customEdge type', () => {
    const steps: WorkflowStep[] = [
      { order: 1, step_id: 'a', name: null, referenced_action_id: 100, on_success_step_id: 'b' },
      { order: 2, step_id: 'b', name: null, referenced_action_id: 101 },
    ];

    const { edges } = workflowStepsToReactFlow(steps);

    const successEdge = edges.find((e) => e.source === 'a' && e.sourceHandle === 'success' && e.target === 'b');
    expect(successEdge).toBeDefined();
    expect(successEdge!.style?.stroke).toBe('#52c41a');
    expect(successEdge!.label).toBe('succès');
    expect(successEdge!.type).toBe('customEdge');
  });

  it('creates error edges with red style', () => {
    const steps: WorkflowStep[] = [
      { order: 1, step_id: 'a', name: null, referenced_action_id: 100, on_error_step_id: 'c' },
      { order: 2, step_id: 'c', name: null, referenced_action_id: 102 },
    ];

    const { edges } = workflowStepsToReactFlow(steps);

    const errorEdge = edges.find((e) => e.source === 'a' && e.sourceHandle === 'error' && e.target === 'c');
    expect(errorEdge).toBeDefined();
    expect(errorEdge!.style?.stroke).toBe('#ff4d4f');
    expect(errorEdge!.label).toBe('erreur');
  });

  it('creates both success and error edges for branching step', () => {
    const steps: WorkflowStep[] = [
      { order: 1, step_id: 'a', name: null, referenced_action_id: 100, on_success_step_id: 'b', on_error_step_id: 'c' },
      { order: 2, step_id: 'b', name: null, referenced_action_id: 101 },
      { order: 3, step_id: 'c', name: null, referenced_action_id: 102 },
    ];

    const { edges } = workflowStepsToReactFlow(steps);

    const successEdge = edges.find((e) => e.source === 'a' && e.sourceHandle === 'success');
    const errorEdge = edges.find((e) => e.source === 'a' && e.sourceHandle === 'error');
    expect(successEdge?.target).toBe('b');
    expect(errorEdge?.target).toBe('c');
  });

  it('positions workflow nodes in a grid layout with Y offset for start node', () => {
    const steps: WorkflowStep[] = Array.from({ length: 5 }, (_, i) => ({
      order: i + 1,
      step_id: `s${i}`,
      name: null,
      referenced_action_id: 100 + i,
    }));

    const { nodes } = workflowStepsToReactFlow(steps);

    // Workflow nodes start at index 1 (after start node), with Y offset of 120
    const wfNodes = nodes.filter((n) => n.id !== START_NODE_ID && n.id !== END_NODE_ID);
    expect(wfNodes[0].position.x).toBe(0);
    expect(wfNodes[0].position.y).toBe(120); // Y offset for start node
    expect(wfNodes[3].position.x).toBe(840); // 3 * 280
    expect(wfNodes[3].position.y).toBe(120);
    expect(wfNodes[4].position.x).toBe(0);
    expect(wfNodes[4].position.y).toBe(320); // 120 + 200
  });

  // Story 16.7: Start/End node injection
  it('injects start node as first node', () => {
    const steps: WorkflowStep[] = [
      { order: 1, step_id: 'a', name: null, referenced_action_id: 100 },
    ];
    const { nodes } = workflowStepsToReactFlow(steps);
    expect(nodes[0].id).toBe(START_NODE_ID);
    expect(nodes[0].type).toBe('start');
    expect(nodes[0].data).toEqual({ isStartNode: true });
  });

  it('injects end node as last node', () => {
    const steps: WorkflowStep[] = [
      { order: 1, step_id: 'a', name: null, referenced_action_id: 100 },
    ];
    const { nodes } = workflowStepsToReactFlow(steps);
    expect(nodes[nodes.length - 1].id).toBe(END_NODE_ID);
    expect(nodes[nodes.length - 1].type).toBe('end');
    expect(nodes[nodes.length - 1].data).toEqual({ isEndNode: true });
  });

  it('connects start to first workflow node', () => {
    const steps: WorkflowStep[] = [
      { order: 1, step_id: 'a', name: null, referenced_action_id: 100 },
    ];
    const { edges } = workflowStepsToReactFlow(steps);
    const startEdge = edges.find((e) => e.source === START_NODE_ID);
    expect(startEdge).toBeDefined();
    expect(startEdge!.target).toBe('a');
  });

  it('connects nodes without output to end node', () => {
    const steps: WorkflowStep[] = [
      { order: 1, step_id: 'a', name: null, referenced_action_id: 100, on_success_step_id: 'b' },
      { order: 2, step_id: 'b', name: null, referenced_action_id: 101 }, // no output
    ];
    const { edges } = workflowStepsToReactFlow(steps);
    // 'b' has no output so should connect to end
    const endEdge = edges.find((e) => e.source === 'b' && e.target === END_NODE_ID);
    expect(endEdge).toBeDefined();
  });

  it('populates on_success_step_id and on_error_step_id in node data for tooltip', () => {
    const steps: WorkflowStep[] = [
      { order: 1, step_id: 'a', name: 'Step A', referenced_action_id: 100, on_success_step_id: 'b', on_error_step_id: 'c' },
      { order: 2, step_id: 'b', name: null, referenced_action_id: 101 },
      { order: 3, step_id: 'c', name: null, referenced_action_id: 102 },
    ];
    const { nodes } = workflowStepsToReactFlow(steps);
    const nodeA = nodes.find((n) => n.id === 'a')!;
    expect((nodeA.data as Record<string, unknown>).on_success_step_id).toBe('b');
    expect((nodeA.data as Record<string, unknown>).on_error_step_id).toBe('c');
  });
});

describe('reactFlowToWorkflowSteps', () => {
  it('converts empty arrays to empty steps', () => {
    const result = reactFlowToWorkflowSteps([], []);
    expect(result).toHaveLength(0);
  });

  it('converts nodes to steps with correct order', () => {
    const nodes: Node[] = [
      {
        id: 'step-1',
        type: 'workflowStep',
        position: { x: 0, y: 0 },
        data: {
          action_id: 100,
          action_name: 'Create PDB',
          action_engine: 'Oracle',
          action_platform: '',
          name: 'My Step',
          retry_enabled: true,
          retry_max_attempts: 5,
          retry_interval_seconds: 30,
          retry_backoff_multiplier: 1.5,
        },
      },
    ];

    const steps = reactFlowToWorkflowSteps(nodes, []);

    expect(steps).toHaveLength(1);
    expect(steps[0].order).toBe(1);
    expect(steps[0].step_id).toBe('step-1');
    expect(steps[0].name).toBe('My Step');
    expect(steps[0].referenced_action_id).toBe(100);
    expect(steps[0].retry_enabled).toBe(true);
    expect(steps[0].retry_max_attempts).toBe(5);
    expect(steps[0].on_success_step_id).toBeNull();
    expect(steps[0].on_error_step_id).toBeNull();
  });

  it('maps edges to on_success_step_id and on_error_step_id', () => {
    const nodes: Node[] = [
      { id: 'a', type: 'workflowStep', position: { x: 0, y: 0 }, data: { action_id: 100, name: null, retry_enabled: false } },
      { id: 'b', type: 'workflowStep', position: { x: 280, y: 0 }, data: { action_id: 101, name: null, retry_enabled: false } },
      { id: 'c', type: 'workflowStep', position: { x: 0, y: 200 }, data: { action_id: 102, name: null, retry_enabled: false } },
    ];

    const edges: Edge[] = [
      { id: 'e1', source: 'a', target: 'b', sourceHandle: 'success' },
      { id: 'e2', source: 'a', target: 'c', sourceHandle: 'error' },
    ];

    const steps = reactFlowToWorkflowSteps(nodes, edges);

    expect(steps[0].on_success_step_id).toBe('b');
    expect(steps[0].on_error_step_id).toBe('c');
    expect(steps[1].on_success_step_id).toBeNull();
    expect(steps[2].on_error_step_id).toBeNull();
  });

  it('round-trips correctly: steps → reactflow → steps', () => {
    const original: WorkflowStep[] = [
      {
        order: 1,
        step_id: 'step-1',
        name: 'Étape un',
        referenced_action_id: 100,
        on_success_step_id: 'step-2',
        on_error_step_id: null,
        retry_enabled: true,
        retry_max_attempts: 3,
        retry_interval_seconds: 60,
        retry_backoff_multiplier: 2.0,
      },
      {
        order: 2,
        step_id: 'step-2',
        name: null,
        referenced_action_id: 101,
        on_success_step_id: null,
        on_error_step_id: null,
        retry_enabled: false,
        retry_max_attempts: null,
        retry_interval_seconds: null,
        retry_backoff_multiplier: null,
      },
    ];

    const { nodes, edges } = workflowStepsToReactFlow(original);
    const roundTripped = reactFlowToWorkflowSteps(nodes, edges);

    expect(roundTripped).toHaveLength(2);
    expect(roundTripped[0].step_id).toBe('step-1');
    expect(roundTripped[0].name).toBe('Étape un');
    expect(roundTripped[0].referenced_action_id).toBe(100);
    expect(roundTripped[0].on_success_step_id).toBe('step-2');
    expect(roundTripped[0].retry_enabled).toBe(true);
    expect(roundTripped[0].retry_max_attempts).toBe(3);

    expect(roundTripped[1].step_id).toBe('step-2');
    expect(roundTripped[1].on_success_step_id).toBeNull();
    expect(roundTripped[1].retry_enabled).toBe(false);
  });

  // Story 16.7: Start/End exclusion
  it('excludes start and end nodes from conversion', () => {
    const nodes: Node[] = [
      { id: START_NODE_ID, type: 'start', position: { x: 0, y: 0 }, data: { isStartNode: true } },
      { id: 'step-1', type: 'workflowStep', position: { x: 0, y: 120 }, data: { action_id: 100, name: null, retry_enabled: false } },
      { id: END_NODE_ID, type: 'end', position: { x: 0, y: 320 }, data: { isEndNode: true } },
    ];
    const edges: Edge[] = [
      { id: 'start-to-1', source: START_NODE_ID, sourceHandle: 'output', target: 'step-1', targetHandle: 'input' },
      { id: '1-to-end', source: 'step-1', sourceHandle: 'success', target: END_NODE_ID, targetHandle: 'input' },
    ];

    const steps = reactFlowToWorkflowSteps(nodes, edges);

    expect(steps).toHaveLength(1);
    expect(steps[0].step_id).toBe('step-1');
    // Edge to END_NODE_ID should be excluded → on_success_step_id = null
    expect(steps[0].on_success_step_id).toBeNull();
  });
});

// ── Unit Tests: Validation ─────────────────────────────────────────────────

describe('validateWorkflowGraph', () => {
  const makeNode = (id: string): Node => ({
    id,
    type: 'workflowStep',
    position: { x: 0, y: 0 },
    data: {
      action_id: 100,
      action_name: 'Test Action',
      action_engine: 'Oracle',
      action_platform: '',
      name: null,
      retry_enabled: false,
    },
  });

  it('returns error for empty graph', () => {
    const result = validateWorkflowGraph([], []);
    expect(result.valid).toBe(false);
    expect(result.errors).toHaveLength(1);
    expect(result.errors[0].type).toBe('error');
    expect(result.errors[0].message).toContain('Au moins une étape');
  });

  it('returns valid for single connected node (warning for no output)', () => {
    const nodes = [makeNode('a')];
    const result = validateWorkflowGraph(nodes, []);

    // Single node with no output is a warning, not an error
    expect(result.valid).toBe(true);
    expect(result.errors.filter((e) => e.type === 'warning')).toHaveLength(1);
  });

  it('detects nodes without output connections as warnings', () => {
    const nodes = [makeNode('a'), makeNode('b')];
    const edges: Edge[] = [
      { id: 'e1', source: 'a', target: 'b', sourceHandle: 'success' },
    ];

    const result = validateWorkflowGraph(nodes, edges);

    // Node 'b' has no output — warning only
    const warnings = result.errors.filter((e) => e.type === 'warning');
    expect(warnings).toHaveLength(1);
    expect(warnings[0].nodeId).toBe('b');
  });

  it('detects orphan nodes (not reachable from start)', () => {
    const nodes = [makeNode('a'), makeNode('b'), makeNode('c')];
    const edges: Edge[] = [
      { id: 'e1', source: 'a', target: 'b', sourceHandle: 'success' },
      // 'c' is not connected — orphan
    ];

    const result = validateWorkflowGraph(nodes, edges);

    const orphanErrors = result.errors.filter(
      (e) => e.type === 'error' && e.message.includes('Non atteignable')
    );
    expect(orphanErrors).toHaveLength(1);
    expect(orphanErrors[0].nodeId).toBe('c');
    expect(result.valid).toBe(false);
  });

  it('detects cycles (infinite loops)', () => {
    const nodes = [makeNode('a'), makeNode('b')];
    const edges: Edge[] = [
      { id: 'e1', source: 'a', target: 'b', sourceHandle: 'success' },
      { id: 'e2', source: 'b', target: 'a', sourceHandle: 'success' },
    ];

    const result = validateWorkflowGraph(nodes, edges);

    const cycleErrors = result.errors.filter(
      (e) => e.type === 'error' && e.message.includes('Boucle infinie')
    );
    expect(cycleErrors.length).toBeGreaterThan(0);
    expect(result.valid).toBe(false);
  });

  it('valid graph with success and error branches', () => {
    const nodes = [makeNode('start'), makeNode('success'), makeNode('error')];
    const edges: Edge[] = [
      { id: 'e1', source: 'start', target: 'success', sourceHandle: 'success' },
      { id: 'e2', source: 'start', target: 'error', sourceHandle: 'error' },
    ];

    const result = validateWorkflowGraph(nodes, edges);

    // success and error nodes have no outputs (warnings), but no errors
    expect(result.valid).toBe(true);
    const errors = result.errors.filter((e) => e.type === 'error');
    expect(errors).toHaveLength(0);
  });

  it('detects self-referencing cycle', () => {
    const nodes = [makeNode('a')];
    const edges: Edge[] = [
      { id: 'e1', source: 'a', target: 'a', sourceHandle: 'error' },
    ];

    const result = validateWorkflowGraph(nodes, edges);
    const cycleErrors = result.errors.filter((e) => e.message.includes('Boucle infinie'));
    expect(cycleErrors.length).toBeGreaterThan(0);
    expect(result.valid).toBe(false);
  });

  it('handles complex valid graph without false positives', () => {
    // start → step1 (success) → step2 (success) → end
    //                  (error) → step3 (success) → end
    const nodes = [makeNode('start'), makeNode('step1'), makeNode('step2'), makeNode('step3')];
    const edges: Edge[] = [
      { id: 'e1', source: 'start', target: 'step1', sourceHandle: 'success' },
      { id: 'e2', source: 'step1', target: 'step2', sourceHandle: 'success' },
      { id: 'e3', source: 'step1', target: 'step3', sourceHandle: 'error' },
    ];

    const result = validateWorkflowGraph(nodes, edges);

    // No orphans, no cycles
    const errors = result.errors.filter((e) => e.type === 'error');
    expect(errors).toHaveLength(0);
    expect(result.valid).toBe(true);
  });

  // Story 16.7: Validation ignores start/end visual nodes
  it('ignores start and end visual nodes in validation', () => {
    const startNode: Node = { id: START_NODE_ID, type: 'start', position: { x: 0, y: 0 }, data: { isStartNode: true } };
    const endNode: Node = { id: END_NODE_ID, type: 'end', position: { x: 0, y: 400 }, data: { isEndNode: true } };
    const wfNode = makeNode('a');

    const nodes = [startNode, wfNode, endNode];
    const edges: Edge[] = [
      { id: 'start-to-a', source: START_NODE_ID, target: 'a', sourceHandle: 'output' },
      { id: 'a-to-end', source: 'a', target: END_NODE_ID, sourceHandle: 'success' },
    ];

    const result = validateWorkflowGraph(nodes, edges);
    // Should validate only 'a'. 'a' has no workflow edges (only to END), so warning
    expect(result.valid).toBe(true);
    // Should not have any errors related to start/end
    expect(result.errors.every((e) => e.nodeId !== START_NODE_ID && e.nodeId !== END_NODE_ID)).toBe(true);
  });
});

// ── Integration Tests: Component Rendering ─────────────────────────────────

// Mock @xyflow/react for component tests
vi.mock('@xyflow/react', async () => {
  const actualReact = await import('react');
  let connectCb: ((params: unknown) => void) | null = null;
  let nodeDoubleClickCb: ((event: unknown, node: unknown) => void) | null = null;

  return {
    ReactFlow: ({ children, nodes, edges, onConnect, onNodeDoubleClick, onDrop, onDragOver, ...rest }: Record<string, unknown>) => {
      connectCb = onConnect as typeof connectCb;
      nodeDoubleClickCb = onNodeDoubleClick as typeof nodeDoubleClickCb;
      return actualReact.createElement('div', { 'data-testid': 'react-flow-canvas', ...rest },
        actualReact.createElement('div', { 'data-testid': 'react-flow-nodes' },
          (nodes as Node[])?.map?.((n: Node) =>
            actualReact.createElement('div', {
              key: n.id,
              'data-testid': `rf-node-${n.id}`,
              'data-node-id': n.id,
              onDoubleClick: (e: unknown) => nodeDoubleClickCb?.(e, n),
            }, (n.data as Record<string, unknown>)?.action_name as string ?? n.id)
          )
        ),
        actualReact.createElement('div', { 'data-testid': 'react-flow-edges' },
          (edges as Edge[])?.map?.((e: Edge) =>
            actualReact.createElement('div', {
              key: e.id,
              'data-testid': `rf-edge-${e.id}`,
              'data-source': e.source,
              'data-target': e.target,
              'data-source-handle': e.sourceHandle,
            })
          )
        ),
        children
      );
    },
    ReactFlowProvider: ({ children }: { children: React.ReactNode }) =>
      actualReact.createElement('div', { 'data-testid': 'react-flow-provider' }, children),
    Controls: () => actualReact.createElement('div', { 'data-testid': 'rf-controls' }),
    MiniMap: () => actualReact.createElement('div', { 'data-testid': 'rf-minimap' }),
    Background: () => null,
    Handle: ({ id, type, position }: { id: string; type: string; position: string }) =>
      actualReact.createElement('div', { 'data-testid': `handle-${id}`, 'data-handle-type': type, 'data-position': position }),
    BaseEdge: () => null,
    EdgeLabelRenderer: ({ children }: { children: React.ReactNode }) =>
      actualReact.createElement('div', { 'data-testid': 'edge-label-renderer' }, children),
    getSmoothStepPath: () => ['M0 0', 0, 0],
    addEdge: (edge: Edge, edges: Edge[]) => [...edges, edge],
    useNodesState: (initial: Node[]) => {
      const [nodes, setNodes] = actualReact.useState(initial);
      return [nodes, setNodes, vi.fn()];
    },
    useEdgesState: (initial: Edge[]) => {
      const [edges, setEdges] = actualReact.useState(initial);
      return [edges, setEdges, vi.fn()];
    },
    useReactFlow: () => ({
      screenToFlowPosition: ({ x, y }: { x: number; y: number }) => ({ x, y }),
      getNode: () => ({ position: { x: 0, y: 0 } }),
      setCenter: vi.fn(),
      setEdges: vi.fn(),
      fitView: vi.fn(),
    }),
    Position: { Top: 'top', Bottom: 'bottom', Left: 'left', Right: 'right' },
  };
});

describe('WorkflowBuilderCanvas Component', () => {
  // Dynamically import to use mocked modules
  let WorkflowBuilderCanvas: React.FC<{
    steps: WorkflowStep[];
    onChange: (steps: WorkflowStep[]) => void;
    disabled?: boolean;
  }>;

  beforeAll(async () => {
    const mod = await import('./WorkflowBuilderCanvas');
    WorkflowBuilderCanvas = mod.WorkflowBuilderCanvas;
  });

  it('renders the canvas with palette, controls, and minimap', async () => {
    const onChange = vi.fn();
    await act(async () => {
      render(<WorkflowBuilderCanvas steps={[]} onChange={onChange} />);
    });

    expect(screen.getByText('Actions disponibles')).toBeInTheDocument();
    expect(screen.getByTestId('react-flow-canvas')).toBeInTheDocument();
    expect(screen.getByTestId('rf-controls')).toBeInTheDocument();
    expect(screen.getByTestId('rf-minimap')).toBeInTheDocument();
  });

  it('renders existing workflow steps as nodes (plus start/end)', async () => {
    const steps: WorkflowStep[] = [
      { order: 1, step_id: 'step-1', name: 'Étape A', referenced_action_id: 100, on_success_step_id: 'step-2' },
      { order: 2, step_id: 'step-2', name: 'Étape B', referenced_action_id: 101 },
    ];
    const onChange = vi.fn();

    await act(async () => {
      render(<WorkflowBuilderCanvas steps={steps} onChange={onChange} />);
    });

    expect(screen.getByTestId('rf-node-step-1')).toBeInTheDocument();
    expect(screen.getByTestId('rf-node-step-2')).toBeInTheDocument();
    // Start/end visual nodes
    expect(screen.getByTestId(`rf-node-${START_NODE_ID}`)).toBeInTheDocument();
    expect(screen.getByTestId(`rf-node-${END_NODE_ID}`)).toBeInTheDocument();
  });

  it('renders edges between connected steps', async () => {
    const steps: WorkflowStep[] = [
      { order: 1, step_id: 'a', name: null, referenced_action_id: 100, on_success_step_id: 'b', on_error_step_id: 'c' },
      { order: 2, step_id: 'b', name: null, referenced_action_id: 101 },
      { order: 3, step_id: 'c', name: null, referenced_action_id: 102 },
    ];
    const onChange = vi.fn();

    await act(async () => {
      render(<WorkflowBuilderCanvas steps={steps} onChange={onChange} />);
    });

    expect(screen.getByTestId('rf-edge-a_success_b')).toBeInTheDocument();
    expect(screen.getByTestId('rf-edge-a_error_c')).toBeInTheDocument();
  });

  it('shows validate button with updated label', async () => {
    const onChange = vi.fn();

    await act(async () => {
      render(<WorkflowBuilderCanvas steps={[]} onChange={onChange} />);
    });

    const validateBtn = screen.getByText('Valider le workflow');
    expect(validateBtn).toBeInTheDocument();
  });

  it('shows action palette with search', async () => {
    const onChange = vi.fn();

    await act(async () => {
      render(<WorkflowBuilderCanvas steps={[]} onChange={onChange} />);
    });

    expect(screen.getByLabelText('Rechercher une action')).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText('Create PDB')).toBeInTheDocument();
      expect(screen.getByText('Apply Patch')).toBeInTheDocument();
      expect(screen.getByText('Backup DB')).toBeInTheDocument();
    });
  });

  it('displays helper text for drag instructions', async () => {
    const onChange = vi.fn();

    await act(async () => {
      render(<WorkflowBuilderCanvas steps={[]} onChange={onChange} />);
    });

    expect(screen.getByText(/Glissez des actions/)).toBeInTheDocument();
  });

  it('disables interaction in disabled mode', async () => {
    const onChange = vi.fn();
    const steps: WorkflowStep[] = [
      { order: 1, step_id: 'step-1', name: 'Step 1', referenced_action_id: 100 },
    ];

    await act(async () => {
      render(<WorkflowBuilderCanvas steps={steps} onChange={onChange} disabled />);
    });

    // Palette search should be disabled
    const searchInput = screen.getByLabelText('Rechercher une action');
    expect(searchInput).toBeDisabled();
  });

  // Story 16.7: Start edge from start to first node
  it('renders start-to-first-node edge', async () => {
    const steps: WorkflowStep[] = [
      { order: 1, step_id: 'a', name: null, referenced_action_id: 100 },
    ];
    const onChange = vi.fn();

    await act(async () => {
      render(<WorkflowBuilderCanvas steps={steps} onChange={onChange} />);
    });

    expect(screen.getByTestId(`rf-edge-${START_NODE_ID}_to_a`)).toBeInTheDocument();
  });
});

// ── Accessibility Tests ────────────────────────────────────────────────────

describe('Accessibility', () => {
  it('palette items have aria-labels for drag', async () => {
    const { WorkflowBuilderCanvas } = await import('./WorkflowBuilderCanvas');
    const onChange = vi.fn();

    await act(async () => {
      render(<WorkflowBuilderCanvas steps={[]} onChange={onChange} />);
    });

    await waitFor(() => {
      expect(screen.getByText('Create PDB')).toBeInTheDocument();
    });

    // Each palette item should have an aria-label
    const paletteItems = screen.getAllByLabelText(/Glisser l'action/);
    expect(paletteItems.length).toBeGreaterThan(0);
  });

  it('search input has aria-label', async () => {
    const { WorkflowBuilderCanvas } = await import('./WorkflowBuilderCanvas');
    const onChange = vi.fn();

    await act(async () => {
      render(<WorkflowBuilderCanvas steps={[]} onChange={onChange} />);
    });

    expect(screen.getByLabelText('Rechercher une action')).toBeInTheDocument();
  });

  // HIGH-4 FIX: Test file input ARIA label
  it('file input has aria-label for screen readers', async () => {
    const { WorkflowBuilderCanvas } = await import('./WorkflowBuilderCanvas');
    const onChange = vi.fn();

    await act(async () => {
      render(<WorkflowBuilderCanvas steps={[]} onChange={onChange} />);
    });

    // File input is hidden but should have aria-label
    const fileInput = document.querySelector('input[type="file"]');
    expect(fileInput).toHaveAttribute('aria-label', 'Sélectionner un fichier workflow à importer');
  });
});

// ── Story 16.8: Export/Import Tests ─────────────────────────────────────────

describe('Story 16.8 — Export/Import', () => {
  let WorkflowBuilderCanvas: React.FC<{
    steps: WorkflowStep[];
    onChange: (steps: WorkflowStep[]) => void;
    disabled?: boolean;
    workflowMetadata?: { name: string; description: string | null; tags: string[] };
    onMetadataImport?: (metadata: { name: string; description: string | null; tags: string[] }) => void;
  }>;

  beforeAll(async () => {
    const mod = await import('./WorkflowBuilderCanvas');
    WorkflowBuilderCanvas = mod.WorkflowBuilderCanvas;
  });

  it('renders Import and Export buttons in toolbar', async () => {
    const onChange = vi.fn();

    await act(async () => {
      render(<WorkflowBuilderCanvas steps={[]} onChange={onChange} />);
    });

    expect(screen.getByLabelText('Importer un workflow')).toBeInTheDocument();
    expect(screen.getByLabelText('Exporter le workflow')).toBeInTheDocument();
  });

  it('renders Import button with "Importer" text', async () => {
    const onChange = vi.fn();

    await act(async () => {
      render(<WorkflowBuilderCanvas steps={[]} onChange={onChange} />);
    });

    expect(screen.getByText('Importer')).toBeInTheDocument();
  });

  it('renders Export button with "Exporter" text', async () => {
    const onChange = vi.fn();

    await act(async () => {
      render(<WorkflowBuilderCanvas steps={[]} onChange={onChange} />);
    });

    expect(screen.getByText('Exporter')).toBeInTheDocument();
  });

  it('renders hidden file input for import', async () => {
    const onChange = vi.fn();

    await act(async () => {
      render(<WorkflowBuilderCanvas steps={[]} onChange={onChange} />);
    });

    const fileInput = screen.getByLabelText('Sélectionner un fichier workflow à importer');
    expect(fileInput).toBeInTheDocument();
    expect(fileInput).toHaveStyle({ display: 'none' });
    expect(fileInput).toHaveAttribute('accept', '.json,.yaml,.yml');
  });

  it('disables Import and Export buttons when disabled prop is true', async () => {
    const onChange = vi.fn();

    await act(async () => {
      render(<WorkflowBuilderCanvas steps={[]} onChange={onChange} disabled />);
    });

    const importBtn = screen.getByLabelText('Importer un workflow');
    const exportBtn = screen.getByLabelText('Exporter le workflow');
    expect(importBtn).toBeDisabled();
    expect(exportBtn).toBeDisabled();
  });

  it('Export and Import buttons have proper ARIA labels', async () => {
    const onChange = vi.fn();

    await act(async () => {
      render(<WorkflowBuilderCanvas steps={[]} onChange={onChange} />);
    });

    expect(screen.getByLabelText('Importer un workflow')).toBeInTheDocument();
    expect(screen.getByLabelText('Exporter le workflow')).toBeInTheDocument();
  });

  it('opens dropdown when Export button is clicked', async () => {
    const onChange = vi.fn();
    const user = userEvent.setup();

    await act(async () => {
      render(<WorkflowBuilderCanvas steps={[]} onChange={onChange} />);
    });

    const exportBtn = screen.getByLabelText('Exporter le workflow');
    await user.click(exportBtn);

    // Dropdown menu items should appear
    await waitFor(() => {
      expect(screen.getByText('Exporter en JSON')).toBeInTheDocument();
      expect(screen.getByText('Exporter en YAML')).toBeInTheDocument();
      expect(screen.getByText("Exporter l'image")).toBeInTheDocument();
    });
  });
});

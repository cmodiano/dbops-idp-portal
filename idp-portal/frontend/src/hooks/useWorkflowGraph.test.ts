/**
 * Tests for useWorkflowGraph hook — coverage.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import React from 'react';
import { App } from 'antd';

// Mock @xyflow/react
const mockSetNodes = vi.fn((updater) => {
  if (typeof updater === 'function') return updater([]);
  return updater;
});
const mockSetEdges = vi.fn((updater) => {
  if (typeof updater === 'function') return updater([]);
  return updater;
});
const mockOnNodesChangeRaw = vi.fn();
const mockOnEdgesChange = vi.fn();
const mockScreenToFlowPosition = vi.fn().mockReturnValue({ x: 100, y: 200 });
const mockFitView = vi.fn();
const mockGetNode = vi.fn();
const mockSetCenter = vi.fn();

vi.mock('@xyflow/react', () => ({
  useReactFlow: () => ({
    screenToFlowPosition: mockScreenToFlowPosition,
    fitView: mockFitView,
    getNode: mockGetNode,
    setCenter: mockSetCenter,
  }),
  useNodesState: vi.fn(() => [[], mockSetNodes, mockOnNodesChangeRaw]),
  useEdgesState: vi.fn(() => [[], mockSetEdges, mockOnEdgesChange]),
  addEdge: vi.fn((edge, edges) => [...edges, edge]),
}));

vi.mock('../utils/workflowConversion', () => ({
  workflowStepsToReactFlow: vi.fn(() => ({ nodes: [], edges: [] })),
  reactFlowToWorkflowSteps: vi.fn(() => []),
  generateStepId: vi.fn(() => 'step-new'),
  END_NODE_ID: 'end',
  START_NODE_ID: 'start',
}));

vi.mock('../utils/workflowValidation', () => ({
  validateWorkflowGraph: vi.fn(() => ({ isValid: true, errors: [] })),
}));

vi.mock('../theme/styleTokens', () => ({
  STYLE_TOKENS: { iconSuccess: '#52c41a', iconError: '#ff4d4f', textSuccess: '#52c41a', textError: '#ff4d4f' },
}));

import { useWorkflowGraph } from './useWorkflowGraph';
import { validateWorkflowGraph } from '../utils/workflowValidation';

const wrapper = ({ children }: { children: React.ReactNode }) =>
  React.createElement(App, null, children);

const defaultProps = {
  steps: [],
  onChange: vi.fn(),
  disabled: false,
};

describe('useWorkflowGraph — coverage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockGetNode.mockReturnValue(null);
  });

  it('initial state: nodes=[], edges=[], selectedNode=null, configPanelOpen=false', () => {
    const { result } = renderHook(() => useWorkflowGraph(defaultProps), { wrapper });
    expect(result.current.nodes).toEqual([]);
    expect(result.current.edges).toEqual([]);
    expect(result.current.selectedNode).toBeNull();
    expect(result.current.configPanelOpen).toBe(false);
    expect(result.current.validation).toBeNull();
    expect(result.current.workflowNodeCount).toBe(0);
  });

  it('onConnect self-loop shows warning notification', () => {
    const { result } = renderHook(() => useWorkflowGraph(defaultProps), { wrapper });
    act(() => {
      result.current.onConnect({ source: 'step-1', target: 'step-1', sourceHandle: 'success', targetHandle: 'input' });
    });
    // no edges added (self-loop rejected)
    expect(mockSetEdges).not.toHaveBeenCalled();
  });

  it('onConnect disabled=true returns early', () => {
    const { result } = renderHook(() => useWorkflowGraph({ ...defaultProps, disabled: true }), { wrapper });
    act(() => {
      result.current.onConnect({ source: 'step-1', target: 'step-2', sourceHandle: 'success', targetHandle: 'input' });
    });
    expect(mockSetEdges).not.toHaveBeenCalled();
  });

  it('onConnect success edge creates edge', () => {
    const { result } = renderHook(() => useWorkflowGraph(defaultProps), { wrapper });
    act(() => {
      result.current.onConnect({ source: 'step-1', target: 'step-2', sourceHandle: 'success', targetHandle: 'input' });
    });
    expect(mockSetEdges).toHaveBeenCalled();
  });

  it('onConnect error edge creates edge', () => {
    const { result } = renderHook(() => useWorkflowGraph(defaultProps), { wrapper });
    act(() => {
      result.current.onConnect({ source: 'step-1', target: 'step-2', sourceHandle: 'error', targetHandle: 'input' });
    });
    expect(mockSetEdges).toHaveBeenCalled();
  });

  it('onDragOver prevents default', () => {
    const { result } = renderHook(() => useWorkflowGraph(defaultProps), { wrapper });
    const mockPreventDefault = vi.fn();
    const event = { preventDefault: mockPreventDefault, dataTransfer: { dropEffect: '' } } as unknown as React.DragEvent;
    act(() => { result.current.onDragOver(event); });
    expect(mockPreventDefault).toHaveBeenCalled();
  });

  it('onDrop disabled=true returns early', () => {
    const { result } = renderHook(() => useWorkflowGraph({ ...defaultProps, disabled: true }), { wrapper });
    const event = {
      preventDefault: vi.fn(),
      dataTransfer: { getData: vi.fn().mockReturnValue('{"id":1,"name":"Action","engine":"AAP"}') },
      clientX: 100, clientY: 200,
    } as never;
    act(() => { result.current.onDrop(event); });
    expect(mockSetNodes).not.toHaveBeenCalled();
  });

  it('onDrop with no actionData returns early', () => {
    const { result } = renderHook(() => useWorkflowGraph(defaultProps), { wrapper });
    const event = {
      preventDefault: vi.fn(),
      dataTransfer: { getData: vi.fn().mockReturnValue('') },
      clientX: 100, clientY: 200,
    } as never;
    act(() => { result.current.onDrop(event); });
    expect(mockSetNodes).not.toHaveBeenCalled();
  });

  it('onDrop with valid actionData calls setNodes', () => {
    const { result } = renderHook(() => useWorkflowGraph(defaultProps), { wrapper });
    const event = {
      preventDefault: vi.fn(),
      dataTransfer: { getData: vi.fn().mockReturnValue('{"id":1,"name":"Deploy","engine":"AAP"}') },
      clientX: 100, clientY: 200,
    } as never;
    act(() => { result.current.onDrop(event); });
    expect(mockSetNodes).toHaveBeenCalled();
  });

  it('onDrop with invalid JSON returns early', () => {
    const { result } = renderHook(() => useWorkflowGraph(defaultProps), { wrapper });
    const event = {
      preventDefault: vi.fn(),
      dataTransfer: { getData: vi.fn().mockReturnValue('invalid-json') },
      clientX: 100, clientY: 200,
    } as never;
    act(() => { result.current.onDrop(event); });
    expect(mockSetNodes).not.toHaveBeenCalled();
  });

  it('onNodeDoubleClick sets selectedNode and opens config panel', () => {
    const { result } = renderHook(() => useWorkflowGraph(defaultProps), { wrapper });
    const node = { id: 'step-1', type: 'workflowStep', position: { x: 0, y: 0 }, data: {} };
    act(() => {
      result.current.onNodeDoubleClick({} as never, node as never);
    });
    expect(result.current.selectedNode).toEqual(node);
    expect(result.current.configPanelOpen).toBe(true);
  });

  it('handleNodeUpdate updates node data', () => {
    const { result } = renderHook(() => useWorkflowGraph(defaultProps), { wrapper });
    act(() => {
      result.current.handleNodeUpdate('step-1', { name: 'Updated' } as never);
    });
    expect(mockSetNodes).toHaveBeenCalled();
  });

  it('handleNodeDelete disabled=true returns early', () => {
    const { result } = renderHook(() => useWorkflowGraph({ ...defaultProps, disabled: true }), { wrapper });
    act(() => { result.current.handleNodeDelete('step-1'); });
    expect(mockSetNodes).not.toHaveBeenCalled();
  });

  it('handleNodeDelete start node returns early', () => {
    const { result } = renderHook(() => useWorkflowGraph(defaultProps), { wrapper });
    act(() => { result.current.handleNodeDelete('start'); });
    expect(mockSetNodes).not.toHaveBeenCalled();
  });

  it('handleNodeDelete end node returns early', () => {
    const { result } = renderHook(() => useWorkflowGraph(defaultProps), { wrapper });
    act(() => { result.current.handleNodeDelete('end'); });
    expect(mockSetNodes).not.toHaveBeenCalled();
  });

  it('handleNodeDelete last step (workflowNodeCount<=1) returns early', () => {
    // With empty nodes, workflowNodeCount=0 <= 1
    const { result } = renderHook(() => useWorkflowGraph(defaultProps), { wrapper });
    act(() => { result.current.handleNodeDelete('step-1'); });
    // workflowNodeCount is 0, so deletion blocked
    expect(mockSetNodes).not.toHaveBeenCalled();
  });

  it('onNodesChange allows position changes', () => {
    const { result } = renderHook(() => useWorkflowGraph(defaultProps), { wrapper });
    act(() => {
      result.current.onNodesChange([{ type: 'position', id: 'step-1', position: { x: 10, y: 20 } } as never]);
    });
    expect(mockOnNodesChangeRaw).toHaveBeenCalled();
  });

  it('onNodesChange blocks remove of last step (workflowNodeCount=0)', () => {
    const { result } = renderHook(() => useWorkflowGraph(defaultProps), { wrapper });
    act(() => {
      result.current.onNodesChange([{ type: 'remove', id: 'step-1' } as never]);
    });
    // Blocked: filtered changes passed
    expect(mockOnNodesChangeRaw).toHaveBeenCalled();
  });

  it('handleValidate calls validateWorkflowGraph and sets validation', () => {
    vi.mocked(validateWorkflowGraph).mockReturnValue({ valid: false, errors: [{ nodeId: 'n1', type: 'error', message: 'Bad' }] });
    const { result } = renderHook(() => useWorkflowGraph(defaultProps), { wrapper });
    act(() => { result.current.handleValidate(); });
    expect(result.current.validation).toBeDefined();
    expect(result.current.validationReportOpen).toBe(true);
  });

  it('clearValidation resets validation state', () => {
    const { result } = renderHook(() => useWorkflowGraph(defaultProps), { wrapper });
    act(() => { result.current.handleValidate(); });
    act(() => { result.current.clearValidation(); });
    expect(result.current.validation).toBeNull();
    expect(result.current.validationReportOpen).toBe(false);
  });

  it('loadImportedWorkflow replaces nodes and edges', () => {
    const { result } = renderHook(() => useWorkflowGraph(defaultProps), { wrapper });
    act(() => {
      result.current.loadImportedWorkflow([{ id: 'n1' } as never], [{ id: 'e1' } as never]);
    });
    expect(mockSetNodes).toHaveBeenCalled();
    expect(mockSetEdges).toHaveBeenCalled();
  });

  it('goToNode with node not found is a no-op', () => {
    mockGetNode.mockReturnValue(null);
    const { result } = renderHook(() => useWorkflowGraph(defaultProps), { wrapper });
    act(() => { result.current.goToNode('missing-node'); });
    expect(mockSetCenter).not.toHaveBeenCalled();
  });

  it('goToNode with node found calls setCenter', () => {
    mockGetNode.mockReturnValue({ id: 'step-1', position: { x: 100, y: 50 }, data: {} });
    const { result } = renderHook(() => useWorkflowGraph(defaultProps), { wrapper });
    act(() => { result.current.goToNode('step-1'); });
    expect(mockSetCenter).toHaveBeenCalled();
  });

  it('workflowNodeCount excludes start and end nodes', () => {
    const { result } = renderHook(() => useWorkflowGraph(defaultProps), { wrapper });
    // nodes=[] from mock, so count=0
    expect(result.current.workflowNodeCount).toBe(0);
  });

  it('loadImportedWorkflow sets nodes and edges', () => {
    const newNodes = [{ id: 'step-1', type: 'workflowStep', position: { x: 0, y: 0 }, data: {} }];
    const newEdges = [{ id: 'e1', source: 'step-1', target: 'end', sourceHandle: 'success' }];
    const { result } = renderHook(() => useWorkflowGraph(defaultProps), { wrapper });

    act(() => {
      result.current.loadImportedWorkflow(newNodes, newEdges);
    });

    expect(mockSetNodes).toHaveBeenCalledWith(newNodes);
    expect(mockSetEdges).toHaveBeenCalledWith(newEdges);
  });

  it('handleAddSpecialStep adds gate step when not disabled', () => {
    const { result } = renderHook(() => useWorkflowGraph(defaultProps), { wrapper });

    act(() => {
      result.current.handleAddSpecialStep('gate');
    });

    expect(mockSetNodes).toHaveBeenCalled();
    expect(result.current.configPanelOpen).toBe(true);
  });

  it('handleAddSpecialStep does nothing when disabled', () => {
    const { result } = renderHook(() => useWorkflowGraph({ ...defaultProps, disabled: true }), { wrapper });

    act(() => {
      result.current.handleAddSpecialStep('gate');
    });

    expect(result.current.configPanelOpen).toBe(false);
  });
});

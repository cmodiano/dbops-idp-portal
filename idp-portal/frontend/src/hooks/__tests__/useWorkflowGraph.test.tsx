/**
 * Tests for useWorkflowGraph hook (Story 54.12 AC4).
 *
 * Covers:
 * - Initialisation depuis steps
 * - onConnect (self-loop rejeté, connexion valide)
 * - onDrop (ajout nœud + auto-connexion depuis Start quand premier step)
 * - handleNodeUpdate (mise à jour data + selectedNode)
 * - handleNodeDelete (guard start/end, guard dernier nœud)
 * - handleValidate (résultat appliqué aux nœuds)
 * - clearValidation (reset état)
 */

import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import type { WorkflowStep } from '../../types/api';
import { START_NODE_ID, END_NODE_ID } from '../../utils/workflowConversion';

// Mock @xyflow/react — identique au pattern WorkflowBuilderCanvas.test.tsx
const mockFitView = vi.fn();
const mockSetCenter = vi.fn();
const mockGetNode = vi.fn();
const mockScreenToFlowPosition = vi.fn(({ x, y }: { x: number; y: number }) => ({ x, y }));

vi.mock('@xyflow/react', async () => {
  const actualReact = await import('react');
  return {
    addEdge: (edge: unknown, edges: unknown[]) => [...edges, edge],
    useNodesState: (initial: unknown[]) => {
      const [nodes, setNodes] = actualReact.useState(initial);
      return [nodes, setNodes, vi.fn()];
    },
    useEdgesState: (initial: unknown[]) => {
      const [edges, setEdges] = actualReact.useState(initial);
      return [edges, setEdges, vi.fn()];
    },
    useReactFlow: () => ({
      screenToFlowPosition: mockScreenToFlowPosition,
      getNode: mockGetNode,
      setCenter: mockSetCenter,
      fitView: mockFitView,
    }),
    Position: { Top: 'top', Bottom: 'bottom', Left: 'left', Right: 'right' },
  };
});

// Mock antd App.useApp()
const mockNotificationWarning = vi.fn();
vi.mock('antd', async () => {
  const actual = await vi.importActual<typeof import('antd')>('antd');
  return {
    ...actual,
    App: {
      ...(actual.App as object),
      useApp: () => ({ notification: { warning: mockNotificationWarning } }),
    },
  };
});

// Import hook after mocks
import { useWorkflowGraph } from '../useWorkflowGraph';

// ── Helpers ─────────────────────────────────────────────────────────────────

const makeSteps = (count: number): WorkflowStep[] =>
  Array.from({ length: count }, (_, i) => ({
    order: i + 1,
    step_id: `step-${i + 1}`,
    name: `Step ${i + 1}`,
    referenced_action_id: 100 + i,
    on_success_step_id: null,
    on_error_step_id: null,
    retry_enabled: false,
    retry_max_attempts: null,
    retry_interval_seconds: null,
    retry_backoff_multiplier: null,
  }));

const makeDropEvent = (actionData: object): React.DragEvent => ({
  preventDefault: vi.fn(),
  clientX: 200,
  clientY: 300,
  dataTransfer: {
    getData: vi.fn().mockReturnValue(JSON.stringify(actionData)),
  },
} as unknown as React.DragEvent);

// ── Tests ────────────────────────────────────────────────────────────────────

describe('useWorkflowGraph — initialisation', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('initialise avec les nœuds convertis depuis steps', () => {
    const steps = makeSteps(2);
    const { result } = renderHook(() =>
      useWorkflowGraph({ steps, onChange: vi.fn() })
    );

    // Start + 2 workflow nodes + End = 4
    expect(result.current.nodes).toHaveLength(4);
    const ids = result.current.nodes.map((n) => n.id);
    expect(ids).toContain(START_NODE_ID);
    expect(ids).toContain(END_NODE_ID);
    expect(ids).toContain('step-1');
    expect(ids).toContain('step-2');
  });

  it('initialise avec des nœuds vides quand steps est vide', () => {
    const { result } = renderHook(() =>
      useWorkflowGraph({ steps: [], onChange: vi.fn() })
    );

    // Start + End uniquement
    expect(result.current.nodes).toHaveLength(2);
    expect(result.current.nodes.map((n) => n.id)).toContain(START_NODE_ID);
    expect(result.current.nodes.map((n) => n.id)).toContain(END_NODE_ID);
  });

  it('initialise configPanelOpen à false', () => {
    const { result } = renderHook(() =>
      useWorkflowGraph({ steps: [], onChange: vi.fn() })
    );
    expect(result.current.configPanelOpen).toBe(false);
  });

  it('initialise validation à null', () => {
    const { result } = renderHook(() =>
      useWorkflowGraph({ steps: [], onChange: vi.fn() })
    );
    expect(result.current.validation).toBeNull();
  });

  it('initialise validationReportOpen à false', () => {
    const { result } = renderHook(() =>
      useWorkflowGraph({ steps: [], onChange: vi.fn() })
    );
    expect(result.current.validationReportOpen).toBe(false);
  });
});

describe('useWorkflowGraph — onConnect', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('déclenche notification.warning pour une self-loop', () => {
    const { result } = renderHook(() =>
      useWorkflowGraph({ steps: makeSteps(1), onChange: vi.fn() })
    );

    act(() => {
      result.current.onConnect({
        source: 'step-1',
        target: 'step-1',
        sourceHandle: 'success',
        targetHandle: 'input',
      });
    });

    expect(mockNotificationWarning).toHaveBeenCalledWith(
      expect.objectContaining({ message: 'Connexion invalide' })
    );
  });

  it('ne déclenche pas de notification pour une connexion valide', () => {
    const { result } = renderHook(() =>
      useWorkflowGraph({ steps: makeSteps(2), onChange: vi.fn() })
    );

    act(() => {
      result.current.onConnect({
        source: 'step-1',
        target: 'step-2',
        sourceHandle: 'success',
        targetHandle: 'input',
      });
    });

    expect(mockNotificationWarning).not.toHaveBeenCalled();
  });

  it('ajoute un edge step-1→step-2 pour une connexion valide', () => {
    const { result } = renderHook(() =>
      useWorkflowGraph({ steps: makeSteps(2), onChange: vi.fn() })
    );

    act(() => {
      result.current.onConnect({
        source: 'step-1',
        target: 'step-2',
        sourceHandle: 'success',
        targetHandle: 'input',
      });
    });

    const newEdge = result.current.edges.find(
      (e) => e.source === 'step-1' && e.target === 'step-2' && e.sourceHandle === 'success'
    );
    expect(newEdge).toBeDefined();
  });

  it('ne traite pas la connexion si disabled=true', () => {
    const { result } = renderHook(() =>
      useWorkflowGraph({ steps: makeSteps(2), onChange: vi.fn(), disabled: true })
    );

    const edgesBefore = result.current.edges.length;

    act(() => {
      result.current.onConnect({
        source: 'step-1',
        target: 'step-2',
        sourceHandle: 'success',
        targetHandle: 'input',
      });
    });

    expect(result.current.edges.length).toBe(edgesBefore);
    expect(mockNotificationWarning).not.toHaveBeenCalled();
  });

  it('Story 67.4: autorise plusieurs edges depuis le même handle (fan-out)', () => {
    const { result } = renderHook(() =>
      useWorkflowGraph({ steps: makeSteps(3), onChange: vi.fn() })
    );

    act(() => {
      result.current.onConnect({
        source: 'step-1',
        target: 'step-2',
        sourceHandle: 'success',
        targetHandle: 'input',
      });
    });

    act(() => {
      result.current.onConnect({
        source: 'step-1',
        target: 'step-3',
        sourceHandle: 'success',
        targetHandle: 'input',
      });
    });

    const successEdgesFromStep1 = result.current.edges.filter(
      (e) => e.source === 'step-1' && e.sourceHandle === 'success'
    );
    // step-1 a au moins 2 edges vers step-2 et step-3 (+ éventuellement end selon état initial)
    expect(successEdgesFromStep1.length).toBeGreaterThanOrEqual(2);
    expect(successEdgesFromStep1.map((e) => e.target)).toContain('step-2');
    expect(successEdgesFromStep1.map((e) => e.target)).toContain('step-3');
  });
});

describe('useWorkflowGraph — onDrop', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('crée un nouveau nœud lors du drop d\'une action', () => {
    const { result } = renderHook(() =>
      useWorkflowGraph({ steps: makeSteps(1), onChange: vi.fn() })
    );

    const nodesBefore = result.current.nodes.length;
    const dropEvent = makeDropEvent({ id: 200, name: 'New Action', engine: 'Oracle' });

    act(() => {
      result.current.onDrop(dropEvent);
    });

    expect(result.current.nodes.length).toBe(nodesBefore + 1);
    const newNode = result.current.nodes.find((n) => n.type === 'workflowStep' && n.id !== 'step-1');
    expect(newNode).toBeDefined();
    expect((newNode!.data as Record<string, unknown>).action_id).toBe(200);
    expect((newNode!.data as Record<string, unknown>).action_name).toBe('New Action');
  });

  it('auto-connecte depuis Start quand c\'est le premier step', () => {
    const { result } = renderHook(() =>
      useWorkflowGraph({ steps: [], onChange: vi.fn() })
    );

    const dropEvent = makeDropEvent({ id: 200, name: 'First Action', engine: 'Oracle' });

    act(() => {
      result.current.onDrop(dropEvent);
    });

    const startEdge = result.current.edges.find(
      (e) => e.source === START_NODE_ID && e.sourceHandle === 'output'
    );
    expect(startEdge).toBeDefined();
  });

  it('ne traite pas le drop si disabled=true', () => {
    const { result } = renderHook(() =>
      useWorkflowGraph({ steps: [], onChange: vi.fn(), disabled: true })
    );

    const nodesBefore = result.current.nodes.length;
    const dropEvent = makeDropEvent({ id: 200, name: 'Action', engine: 'Oracle' });

    act(() => {
      result.current.onDrop(dropEvent);
    });

    expect(result.current.nodes.length).toBe(nodesBefore);
  });

  it('ignore le drop si pas de données d\'action', () => {
    const { result } = renderHook(() =>
      useWorkflowGraph({ steps: [], onChange: vi.fn() })
    );

    const nodesBefore = result.current.nodes.length;
    const emptyDropEvent = {
      preventDefault: vi.fn(),
      clientX: 200,
      clientY: 300,
      dataTransfer: { getData: vi.fn().mockReturnValue('') },
    } as unknown as React.DragEvent;

    act(() => {
      result.current.onDrop(emptyDropEvent);
    });

    expect(result.current.nodes.length).toBe(nodesBefore);
  });
});

describe('useWorkflowGraph — handleNodeUpdate', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('met à jour les données du nœud', () => {
    const { result } = renderHook(() =>
      useWorkflowGraph({ steps: makeSteps(1), onChange: vi.fn() })
    );

    act(() => {
      result.current.handleNodeUpdate('step-1', { name: 'Updated Name' });
    });

    const updatedNode = result.current.nodes.find((n) => n.id === 'step-1');
    expect((updatedNode!.data as Record<string, unknown>).name).toBe('Updated Name');
  });

  it('met à jour selectedNode si le nœud sélectionné est modifié', () => {
    const { result } = renderHook(() =>
      useWorkflowGraph({ steps: makeSteps(1), onChange: vi.fn() })
    );

    // Ouvrir le panneau config sur step-1
    act(() => {
      result.current.onNodeDoubleClick(
        {} as React.MouseEvent,
        result.current.nodes.find((n) => n.id === 'step-1')!
      );
    });

    expect(result.current.selectedNode?.id).toBe('step-1');

    act(() => {
      result.current.handleNodeUpdate('step-1', { name: 'Updated via Panel' });
    });

    expect((result.current.selectedNode!.data as Record<string, unknown>).name).toBe('Updated via Panel');
  });
});

describe('useWorkflowGraph — handleNodeDelete', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('supprime un nœud quand il y a plusieurs étapes', () => {
    const { result } = renderHook(() =>
      useWorkflowGraph({ steps: makeSteps(2), onChange: vi.fn() })
    );

    const nodesBefore = result.current.nodes.length;

    act(() => {
      result.current.handleNodeDelete('step-1');
    });

    expect(result.current.nodes.length).toBe(nodesBefore - 1);
    expect(result.current.nodes.find((n) => n.id === 'step-1')).toBeUndefined();
  });

  it('ne supprime pas le dernier nœud workflow (guard)', () => {
    const { result } = renderHook(() =>
      useWorkflowGraph({ steps: makeSteps(1), onChange: vi.fn() })
    );

    const nodesBefore = result.current.nodes.length;

    act(() => {
      result.current.handleNodeDelete('step-1');
    });

    // Rien ne doit être supprimé
    expect(result.current.nodes.length).toBe(nodesBefore);
  });

  it('ne supprime pas le nœud Start (guard)', () => {
    const { result } = renderHook(() =>
      useWorkflowGraph({ steps: makeSteps(2), onChange: vi.fn() })
    );

    const nodesBefore = result.current.nodes.length;

    act(() => {
      result.current.handleNodeDelete(START_NODE_ID);
    });

    expect(result.current.nodes.length).toBe(nodesBefore);
  });

  it('ne supprime pas le nœud End (guard)', () => {
    const { result } = renderHook(() =>
      useWorkflowGraph({ steps: makeSteps(2), onChange: vi.fn() })
    );

    const nodesBefore = result.current.nodes.length;

    act(() => {
      result.current.handleNodeDelete(END_NODE_ID);
    });

    expect(result.current.nodes.length).toBe(nodesBefore);
  });

  it('ne supprime pas si disabled=true', () => {
    const { result } = renderHook(() =>
      useWorkflowGraph({ steps: makeSteps(2), onChange: vi.fn(), disabled: true })
    );

    const nodesBefore = result.current.nodes.length;

    act(() => {
      result.current.handleNodeDelete('step-1');
    });

    expect(result.current.nodes.length).toBe(nodesBefore);
  });
});

describe('useWorkflowGraph — handleValidate', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('appelle validateWorkflowGraph et met à jour validation', () => {
    const { result } = renderHook(() =>
      useWorkflowGraph({ steps: makeSteps(1), onChange: vi.fn() })
    );

    act(() => {
      result.current.handleValidate();
    });

    expect(result.current.validation).not.toBeNull();
  });

  it('ouvre validationReportOpen après validation', () => {
    const { result } = renderHook(() =>
      useWorkflowGraph({ steps: makeSteps(1), onChange: vi.fn() })
    );

    expect(result.current.validationReportOpen).toBe(false);

    act(() => {
      result.current.handleValidate();
    });

    expect(result.current.validationReportOpen).toBe(true);
  });

  it('applique les statuts de validation aux nœuds via applyValidation', () => {
    const { result } = renderHook(() =>
      useWorkflowGraph({ steps: makeSteps(2), onChange: vi.fn() })
    );

    act(() => {
      result.current.handleValidate();
    });

    expect(result.current.validation).not.toBeNull();
    // applyValidation must have been called: every node gets validationStatus explicitly set
    // (null = no issue, 'error'/'warning' = validation finding)
    result.current.nodes.forEach((node) => {
      const data = node.data as Record<string, unknown>;
      expect(['error', 'warning', null]).toContain(data.validationStatus);
      expect(data).toHaveProperty('validationMessage');
    });
  });
});

describe('useWorkflowGraph — clearValidation', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('remet validation à null', () => {
    const { result } = renderHook(() =>
      useWorkflowGraph({ steps: makeSteps(1), onChange: vi.fn() })
    );

    act(() => {
      result.current.handleValidate();
    });
    expect(result.current.validation).not.toBeNull();

    act(() => {
      result.current.clearValidation();
    });

    expect(result.current.validation).toBeNull();
  });

  it('ferme validationReportOpen', () => {
    const { result } = renderHook(() =>
      useWorkflowGraph({ steps: makeSteps(1), onChange: vi.fn() })
    );

    act(() => {
      result.current.handleValidate();
    });
    expect(result.current.validationReportOpen).toBe(true);

    act(() => {
      result.current.clearValidation();
    });

    expect(result.current.validationReportOpen).toBe(false);
  });

  it('remet validationStatus et validationMessage à null sur tous les nœuds', () => {
    const { result } = renderHook(() =>
      useWorkflowGraph({ steps: makeSteps(1), onChange: vi.fn() })
    );

    act(() => {
      result.current.handleValidate();
    });

    act(() => {
      result.current.clearValidation();
    });

    result.current.nodes.forEach((node) => {
      const data = node.data as Record<string, unknown>;
      expect(data.validationStatus).toBeNull();
      expect(data.validationMessage).toBeNull();
    });
  });
});

describe('useWorkflowGraph — onNodeDoubleClick', () => {
  it('ouvre le configPanel et sélectionne le nœud', () => {
    const { result } = renderHook(() =>
      useWorkflowGraph({ steps: makeSteps(1), onChange: vi.fn() })
    );

    const node = result.current.nodes.find((n) => n.id === 'step-1')!;

    act(() => {
      result.current.onNodeDoubleClick({} as React.MouseEvent, node);
    });

    expect(result.current.configPanelOpen).toBe(true);
    expect(result.current.selectedNode?.id).toBe('step-1');
  });
});

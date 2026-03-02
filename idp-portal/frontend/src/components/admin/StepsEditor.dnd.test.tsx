/**
 * Tests for StepsEditor — drag-and-drop coverage (Story 55.6).
 * Covers lines 391-402 (handleDragEnd with actual reordering).
 * Uses vi.mock to intercept DndContext and capture onDragEnd for direct invocation.
 */

import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, act } from '@testing-library/react';
import type { ExecutionStep } from '../../types/api';

// Capture the onDragEnd callback from DndContext before component renders
let capturedOnDragEnd: ((event: unknown) => void) | null = null;

vi.mock('@dnd-kit/core', async () => {
  const actual = await vi.importActual<typeof import('@dnd-kit/core')>('@dnd-kit/core');
  return {
    ...actual,
    DndContext: ({
      children,
      onDragEnd,
    }: {
      children: React.ReactNode;
      onDragEnd: (event: unknown) => void;
    }) => {
      capturedOnDragEnd = onDragEnd;
      return React.createElement('div', { 'data-testid': 'dnd-context' }, children);
    },
  };
});

vi.mock('../../hooks/useEnvironments', () => ({
  useEnvironments: vi.fn().mockReturnValue({
    environments: ['dev', 'staging', 'prod'],
    environmentOptions: [
      { value: 'dev', label: 'Développement' },
      { value: 'staging', label: 'Staging' },
      { value: 'prod', label: 'Production' },
    ],
    loading: false,
    error: null,
  }),
}));

vi.mock('../../hooks/useAAPTemplates', () => ({
  useAAPTemplates: vi.fn().mockReturnValue({
    templates: [],
    loading: false,
    fallback: true,
    error: null,
  }),
}));

// Import AFTER mocking
import { StepsEditor } from './StepsEditor';

describe('StepsEditor — DnD coverage (lignes 391-402)', () => {
  beforeEach(() => {
    capturedOnDragEnd = null;
  });

  it('handleDragEnd — réordonne les étapes quand active.id !== over.id (lignes 391-402)', () => {
    const onChange = vi.fn();
    const steps: ExecutionStep[] = [
      { order: 1, name: 'Step A', type: 'prerequisite', connector_type: 'none', conditional_environments: null },
      { order: 2, name: 'Step B', type: 'execution', connector_type: 'none', conditional_environments: null },
      { order: 3, name: 'Step C', type: 'verification', connector_type: 'none', conditional_environments: null },
    ];

    render(<StepsEditor value={steps} onChange={onChange} />);

    expect(capturedOnDragEnd).not.toBeNull();

    // Simulate dragging Step A (id="1") to Step C's position (id="3")
    act(() => {
      capturedOnDragEnd!({ active: { id: '1' }, over: { id: '3' } });
    });

    // onChange should be called with reordered steps
    expect(onChange).toHaveBeenCalledTimes(1);

    const reordered = onChange.mock.calls[0][0] as ExecutionStep[];
    expect(reordered).toHaveLength(3);

    // After moving step with order=1 to position of order=3:
    // arrayMove([A,B,C], 0, 2) → [B,C,A]
    // Then map with order: i+1
    expect(reordered[0].name).toBe('Step B');
    expect(reordered[0].order).toBe(1);
    expect(reordered[1].name).toBe('Step C');
    expect(reordered[1].order).toBe(2);
    expect(reordered[2].name).toBe('Step A');
    expect(reordered[2].order).toBe(3);
  });

  it('handleDragEnd — réordonne du bas vers le haut (ligne 394-399)', () => {
    const onChange = vi.fn();
    const steps: ExecutionStep[] = [
      { order: 1, name: 'First', type: 'prerequisite', connector_type: 'none', conditional_environments: null },
      { order: 2, name: 'Second', type: 'execution', connector_type: 'none', conditional_environments: null },
    ];

    render(<StepsEditor value={steps} onChange={onChange} />);

    expect(capturedOnDragEnd).not.toBeNull();

    // Move Second (id="2") to First's position (id="1")
    act(() => {
      capturedOnDragEnd!({ active: { id: '2' }, over: { id: '1' } });
    });

    expect(onChange).toHaveBeenCalledTimes(1);

    const reordered = onChange.mock.calls[0][0] as ExecutionStep[];
    expect(reordered[0].name).toBe('Second');
    expect(reordered[0].order).toBe(1);
    expect(reordered[1].name).toBe('First');
    expect(reordered[1].order).toBe(2);
  });

  it('handleDragEnd — no-op quand over est null (ligne 393 guard)', () => {
    const onChange = vi.fn();
    const steps: ExecutionStep[] = [
      { order: 1, name: 'Only', type: 'execution', connector_type: 'none', conditional_environments: null },
    ];

    render(<StepsEditor value={steps} onChange={onChange} />);

    expect(capturedOnDragEnd).not.toBeNull();

    act(() => {
      capturedOnDragEnd!({ active: { id: '1' }, over: null });
    });

    // No reorder when over is null
    expect(onChange).not.toHaveBeenCalled();
  });

  it('handleDragEnd — no-op quand active.id === over.id (ligne 393 guard)', () => {
    const onChange = vi.fn();
    const steps: ExecutionStep[] = [
      { order: 1, name: 'Alpha', type: 'prerequisite', connector_type: 'none', conditional_environments: null },
      { order: 2, name: 'Beta', type: 'execution', connector_type: 'none', conditional_environments: null },
    ];

    render(<StepsEditor value={steps} onChange={onChange} />);

    expect(capturedOnDragEnd).not.toBeNull();

    // Same id — no reorder
    act(() => {
      capturedOnDragEnd!({ active: { id: '1' }, over: { id: '1' } });
    });

    expect(onChange).not.toHaveBeenCalled();
    // Steps are still in original order
    expect(screen.getByLabelText(/Nom etape 1/i)).toHaveValue('Alpha');
    expect(screen.getByLabelText(/Nom etape 2/i)).toHaveValue('Beta');
  });

  it('handleDragEnd — steps get correct order integers after reorder (ligne 399)', () => {
    const onChange = vi.fn();
    const steps: ExecutionStep[] = [
      { order: 1, name: 'X', type: 'prerequisite', connector_type: 'none', conditional_environments: null },
      { order: 2, name: 'Y', type: 'execution', connector_type: 'none', conditional_environments: null },
      { order: 3, name: 'Z', type: 'verification', connector_type: 'none', conditional_environments: null },
      { order: 4, name: 'W', type: 'prerequisite', connector_type: 'none', conditional_environments: null },
    ];

    render(<StepsEditor value={steps} onChange={onChange} />);

    expect(capturedOnDragEnd).not.toBeNull();

    // Move Z (id="3") to position after X (id="1") → between X and Y
    act(() => {
      capturedOnDragEnd!({ active: { id: '3' }, over: { id: '1' } });
    });

    expect(onChange).toHaveBeenCalledTimes(1);

    const reordered = onChange.mock.calls[0][0] as ExecutionStep[];
    // All reordered steps should have sequential order values starting from 1
    reordered.forEach((step, i) => {
      expect(step.order).toBe(i + 1);
    });
  });
});

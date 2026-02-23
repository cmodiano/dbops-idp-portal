/**
 * StartNode tests (Story 16.7, AC1).
 */

import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';

// Mock @xyflow/react
vi.mock('@xyflow/react', () => ({
  Handle: ({ id, type }: { id: string; type: string }) =>
    React.createElement('div', { 'data-testid': `handle-${id}`, 'data-handle-type': type }),
  Position: { Top: 'top', Bottom: 'bottom', Left: 'left', Right: 'right' },
}));

import StartNode from './StartNode';

const makeProps = () => ({
  id: '__start__',
  type: 'start' as const,
  data: { isStartNode: true },
  selected: false,
  dragging: false,
  draggable: false,
  selectable: false,
  deletable: false,
  zIndex: 0,
  isConnectable: true,
  positionAbsoluteX: 0,
  positionAbsoluteY: 0,
});

describe('StartNode', () => {
  it('renders "Départ" label', () => {
    render(<StartNode {...makeProps()} />);
    expect(screen.getByText('Départ')).toBeInTheDocument();
  });

  it('has green border style', () => {
    render(<StartNode {...makeProps()} />);
    const node = screen.getByRole('img', { name: 'Nœud de départ' });
    expect(node).toBeInTheDocument();
    expect(node.style.border).toMatch(/#52c41a|rgb\(82,\s*196,\s*26\)/);
  });

  it('has a source handle at the bottom', () => {
    render(<StartNode {...makeProps()} />);
    const handle = screen.getByTestId('handle-output');
    expect(handle).toBeInTheDocument();
    expect(handle.getAttribute('data-handle-type')).toBe('source');
  });

  it('has ARIA label for accessibility', () => {
    render(<StartNode {...makeProps()} />);
    expect(screen.getByRole('img', { name: 'Nœud de départ' })).toBeInTheDocument();
  });
});

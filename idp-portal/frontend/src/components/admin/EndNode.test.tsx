/**
 * EndNode tests (Story 16.7, AC1).
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

import EndNode from './EndNode';

const makeProps = () => ({
  id: '__end__',
  type: 'end' as const,
  data: { isEndNode: true },
  selected: false,
  dragging: false,
  zIndex: 0,
  isConnectable: true,
  positionAbsoluteX: 0,
  positionAbsoluteY: 0,
});

describe('EndNode', () => {
  it('renders "Fin" label', () => {
    render(<EndNode {...makeProps()} />);
    expect(screen.getByText('Fin')).toBeInTheDocument();
  });

  it('has grey border style', () => {
    render(<EndNode {...makeProps()} />);
    const node = screen.getByRole('img', { name: 'Nœud de fin' });
    expect(node).toBeInTheDocument();
    expect(node.style.border).toMatch(/#8c8c8c|rgb\(140,\s*140,\s*140\)/);
  });

  it('has a target handle at the top', () => {
    render(<EndNode {...makeProps()} />);
    const handle = screen.getByTestId('handle-input');
    expect(handle).toBeInTheDocument();
    expect(handle.getAttribute('data-handle-type')).toBe('target');
  });

  it('has ARIA label for accessibility', () => {
    render(<EndNode {...makeProps()} />);
    expect(screen.getByRole('img', { name: 'Nœud de fin' })).toBeInTheDocument();
  });
});

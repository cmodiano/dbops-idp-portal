/**
 * CustomEdge tests (Story 16.7, AC5).
 */

import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';

const mockSetEdges = vi.fn();

// Mock @xyflow/react
vi.mock('@xyflow/react', () => ({
  BaseEdge: ({ id, style }: { id: string; style: Record<string, unknown> }) =>
    React.createElement('path', { 'data-testid': `edge-path-${id}`, style }),
  EdgeLabelRenderer: ({ children }: { children: React.ReactNode }) =>
    React.createElement('div', { 'data-testid': 'edge-label-renderer' }, children),
  getSmoothStepPath: () => ['M0 0', 100, 100],
  useReactFlow: () => ({
    setEdges: mockSetEdges,
  }),
  Position: { Top: 'top', Bottom: 'bottom', Left: 'left', Right: 'right' },
}));

import CustomEdge from './CustomEdge';

const makeProps = (overrides: Record<string, unknown> = {}) => ({
  id: 'edge-1',
  source: 'a',
  target: 'b',
  sourceX: 0,
  sourceY: 0,
  targetX: 200,
  targetY: 200,
  sourcePosition: 'bottom' as const,
  targetPosition: 'top' as const,
  style: { stroke: '#52c41a', strokeWidth: 2 },
  label: 'succès',
  labelStyle: { fontSize: 10, fill: '#52c41a' },
  selected: false,
  ...overrides,
});

describe('CustomEdge', () => {
  it('renders the edge path', () => {
    render(<CustomEdge {...(makeProps() as any)} />);
    expect(screen.getByTestId('edge-path-edge-1')).toBeInTheDocument();
  });

  it('renders label text', () => {
    render(<CustomEdge {...(makeProps() as any)} />);
    expect(screen.getByText('succès')).toBeInTheDocument();
  });

  it('does not show context menu when not selected', () => {
    render(<CustomEdge {...(makeProps() as any)} />);
    expect(screen.queryByLabelText('Menu connexion')).not.toBeInTheDocument();
  });

  it('shows context menu button when selected', () => {
    render(<CustomEdge {...(makeProps({ selected: true }) as any)} />);
    expect(screen.getByLabelText('Menu connexion')).toBeInTheDocument();
  });

  it('applies glow style when selected', () => {
    render(<CustomEdge {...(makeProps({ selected: true }) as any)} />);
    const path = screen.getByTestId('edge-path-edge-1');
    expect(path.style.strokeWidth).toBe('3');
  });
});

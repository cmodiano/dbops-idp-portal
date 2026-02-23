/**
 * Tests for WorkflowValidationAlert — Story 26.5 AC8
 */
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { WorkflowValidationAlert } from '../WorkflowValidationAlert';

describe('WorkflowValidationAlert', () => {
  it('renders null when validation is null', () => {
    const { container } = render(<WorkflowValidationAlert validation={null} />);
    expect(container.innerHTML).toBe('');
  });

  it('renders success alert when validation.valid is true', () => {
    render(<WorkflowValidationAlert validation={{ valid: true, errors: [] }} />);
    expect(screen.getByText('Workflow valide')).toBeInTheDocument();
  });

  it('renders error alert with counts when validation.valid is false', () => {
    const validation = {
      valid: false,
      errors: [
        { nodeId: 'a', type: 'error' as const, message: 'err1' },
        { nodeId: 'b', type: 'error' as const, message: 'err2' },
        { nodeId: 'c', type: 'warning' as const, message: 'warn1' },
      ],
    };
    render(<WorkflowValidationAlert validation={validation} />);
    expect(screen.getByText('2 erreur(s), 1 avertissement(s)')).toBeInTheDocument();
  });

  it('renders error alert with zero warnings when all are errors', () => {
    const validation = {
      valid: false,
      errors: [
        { nodeId: 'a', type: 'error' as const, message: 'err1' },
      ],
    };
    render(<WorkflowValidationAlert validation={validation} />);
    expect(screen.getByText('1 erreur(s), 0 avertissement(s)')).toBeInTheDocument();
  });
});

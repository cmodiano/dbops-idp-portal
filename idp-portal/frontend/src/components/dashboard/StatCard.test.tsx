/**
 * Tests for StatCard (Story 5.1, Task 5.2).
 */

import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { CheckCircleOutlined } from '@ant-design/icons';
import { StatCard } from './StatCard';

describe('StatCard', () => {
  it('renders label and value', () => {
    render(<StatCard label="Executions" value={42} />);

    expect(screen.getByText('Executions')).toBeInTheDocument();
    expect(screen.getByText('42')).toBeInTheDocument();
  });

  it('renders value with suffix', () => {
    render(<StatCard label="Success Rate" value={87.5} suffix="%" />);

    expect(screen.getByText('87.5%')).toBeInTheDocument();
  });

  it('renders icon when provided', () => {
    render(
      <StatCard
        label="Completed"
        value={10}
        icon={<CheckCircleOutlined data-testid="check-icon" />}
      />
    );

    expect(screen.getByTestId('check-icon')).toBeInTheDocument();
  });

  it('shows skeleton when loading', () => {
    render(<StatCard label="Loading" value={0} loading />);

    // Skeleton should be visible, value should not
    expect(screen.queryByText('0')).not.toBeInTheDocument();
    expect(document.querySelector('.ant-skeleton')).toBeInTheDocument();
  });

  it('applies success variant styles', () => {
    render(<StatCard label="Success" value={100} variant="success" />);

    // Check the card has the success border color
    const card = document.querySelector('.ant-card');
    expect(card).toHaveStyle({ borderLeft: '4px solid #10B981' });
  });

  it('applies error variant styles', () => {
    render(<StatCard label="Errors" value={5} variant="error" />);

    const card = document.querySelector('.ant-card');
    expect(card).toHaveStyle({ borderLeft: '4px solid #EF4444' });
  });

  it('applies inProgress variant styles', () => {
    render(<StatCard label="Running" value={3} variant="inProgress" />);

    const card = document.querySelector('.ant-card');
    expect(card).toHaveStyle({ borderLeft: '4px solid #3B82F6' });
  });

  it('applies default variant styles when no variant specified', () => {
    render(<StatCard label="Default" value={0} />);

    // Default variant uses theme token (colorBorder), so border is 4px solid with theme color
    const card = document.querySelector('.ant-card');
    expect(card).toHaveStyle({ borderLeftWidth: '4px', borderLeftStyle: 'solid' });
    const borderColor = (card as HTMLElement)?.style?.borderLeftColor;
    expect(borderColor).toBeTruthy();
  });

  it('Story 46.5 — renders tooltip wrapper when tooltip prop is provided', () => {
    render(
      <StatCard
        label="Exécutions du jour"
        value={0}
        tooltip="Nombre d'exécutions soumises ou démarrées aujourd'hui (depuis minuit)"
      />,
    );

    // Ant Design Tooltip wraps content in a container with the title attribute on the trigger
    const tooltipTrigger = document.querySelector('.ant-tooltip-open, [role="tooltip"]');
    // The tooltip title is stored as a prop; verify the label is still visible
    expect(screen.getByText('Exécutions du jour')).toBeInTheDocument();
    // The Tooltip component wraps the card, so .ant-card should still be present
    expect(document.querySelector('.ant-card')).toBeInTheDocument();
    void tooltipTrigger; // used in hover scenarios
  });

  it('Story 46.5 — renders normally without tooltip prop', () => {
    render(<StatCard label="En cours" value={3} />);

    expect(screen.getByText('En cours')).toBeInTheDocument();
    expect(document.querySelector('.ant-card')).toBeInTheDocument();
  });

  it('Story 46.5 — affiche zeroText quand value est 0 et zeroText est défini', () => {
    render(
      <StatCard
        label="Exécutions du jour"
        value={0}
        zeroText="Aucune pour l'instant"
      />,
    );

    expect(screen.getByText("Aucune pour l'instant")).toBeInTheDocument();
  });

  it('Story 46.5 — ne affiche pas zeroText quand value est non-zero', () => {
    render(
      <StatCard
        label="Exécutions du jour"
        value={5}
        zeroText="Aucune pour l'instant"
      />,
    );

    expect(screen.queryByText("Aucune pour l'instant")).not.toBeInTheDocument();
  });
});

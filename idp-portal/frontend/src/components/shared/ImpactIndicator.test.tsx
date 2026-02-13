import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ImpactIndicator } from './ImpactIndicator';

describe('ImpactIndicator', () => {
  it('renders low impact with correct label and aria-label', () => {
    render(<ImpactIndicator level="low" />);

    expect(screen.getByText('Faible')).toBeInTheDocument();
    expect(screen.getByRole('status')).toHaveAttribute('aria-label', 'Impact: Faible');
  });

  it('renders medium impact with correct label and aria-label', () => {
    render(<ImpactIndicator level="medium" />);

    expect(screen.getByText('Moyen')).toBeInTheDocument();
    expect(screen.getByRole('status')).toHaveAttribute('aria-label', 'Impact: Moyen');
  });

  it('renders high impact with correct label and aria-label', () => {
    render(<ImpactIndicator level="high" />);

    expect(screen.getByText('Eleve')).toBeInTheDocument();
    expect(screen.getByRole('status')).toHaveAttribute('aria-label', 'Impact: Eleve');
  });

  it('renders critical impact with correct label and aria-label', () => {
    render(<ImpactIndicator level="critical" />);

    expect(screen.getByText('Critique')).toBeInTheDocument();
    expect(screen.getByRole('status')).toHaveAttribute('aria-label', 'Impact: Critique');
  });

  it('renders small size variant with smaller styling', () => {
    render(<ImpactIndicator level="low" size="small" />);

    const tag = screen.getByText('Faible').closest('.ant-tag');
    expect(tag).toHaveStyle({ fontSize: '12px' });
  });

  it('renders default size without small styling override', () => {
    render(<ImpactIndicator level="low" size="default" />);

    // Just verify the tag renders correctly - default styling is managed by Ant Design
    expect(screen.getByText('Faible')).toBeInTheDocument();
    expect(screen.getByRole('status')).toBeInTheDocument();
  });
});

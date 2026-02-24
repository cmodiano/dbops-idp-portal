/**
 * Tests for CronExpressionHelper component (Story 39.7 — coverage).
 */
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import CronExpressionHelper from './CronExpressionHelper';

describe('CronExpressionHelper', () => {
  const defaultProps = {
    open: true,
    onClose: vi.fn(),
  };

  it('renders the modal when open=true', () => {
    render(<CronExpressionHelper {...defaultProps} />);
    expect(screen.getByText('Aide - Expressions Cron')).toBeInTheDocument();
  });

  it('does not render modal content when open=false', () => {
    render(<CronExpressionHelper open={false} onClose={vi.fn()} />);
    expect(screen.queryByText('Aide - Expressions Cron')).not.toBeInTheDocument();
  });

  it('displays the cron format explanation', () => {
    render(<CronExpressionHelper {...defaultProps} />);
    expect(screen.getByText(/minute heure jour mois/i)).toBeInTheDocument();
  });

  it('displays the fields table', () => {
    render(<CronExpressionHelper {...defaultProps} />);
    expect(screen.getByText('Tableau des champs')).toBeInTheDocument();
  });

  it('displays the examples table', () => {
    render(<CronExpressionHelper {...defaultProps} />);
    expect(screen.getByText('Exemples annotés')).toBeInTheDocument();
  });

  it('displays the special characters section', () => {
    render(<CronExpressionHelper {...defaultProps} />);
    expect(screen.getByText('Caractères spéciaux')).toBeInTheDocument();
  });

  it('calls onClose when Fermer button is clicked', () => {
    const onClose = vi.fn();
    render(<CronExpressionHelper open={true} onClose={onClose} />);
    fireEvent.click(screen.getByText('Fermer'));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('displays crontab.guru link', () => {
    render(<CronExpressionHelper {...defaultProps} />);
    expect(screen.getByText(/crontab\.guru/i)).toBeInTheDocument();
  });

  it('shows field header columns', () => {
    render(<CronExpressionHelper {...defaultProps} />);
    expect(screen.getByText('Champ')).toBeInTheDocument();
    expect(screen.getAllByText('Description').length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('Valeurs possibles')).toBeInTheDocument();
    expect(screen.getAllByText('Exemples').length).toBeGreaterThanOrEqual(1);
  });

  it('shows expression column in examples table', () => {
    render(<CronExpressionHelper {...defaultProps} />);
    expect(screen.getByText('Expression')).toBeInTheDocument();
  });
});

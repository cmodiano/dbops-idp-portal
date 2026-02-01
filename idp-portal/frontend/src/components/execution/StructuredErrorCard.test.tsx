/**
 * Tests for StructuredErrorCard (Story 4.7, AC2, AC5, Task 2.4, 6.2).
 *
 * Rendu Quoi/Pourquoi/Options, role="alert", aria-labelledby, callbacks.
 */

import { describe, it, expect, vi } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { StructuredErrorCard } from './StructuredErrorCard';

describe('StructuredErrorCard', () => {
  const defaultProps = {
    quoi: 'Étape Platform a échoué',
    pourquoi: 'Connection timeout après 30s',
  };

  it('renders Quoi and Pourquoi sections', () => {
    render(<StructuredErrorCard {...defaultProps} />);
    expect(screen.getByText('Quoi')).toBeInTheDocument();
    expect(screen.getByText('Pourquoi')).toBeInTheDocument();
    expect(screen.getByText('Étape Platform a échoué')).toBeInTheDocument();
    expect(screen.getByText('Connection timeout après 30s')).toBeInTheDocument();
  });

  it('has role="alert" for accessibility (AC5)', () => {
    render(<StructuredErrorCard {...defaultProps} />);
    const alert = screen.getByRole('alert');
    expect(alert).toBeInTheDocument();
  });

  it('renders Options: Relancer, Voir logs, Contacter DBA', () => {
    render(<StructuredErrorCard {...defaultProps} />);
    expect(screen.getByRole('button', { name: /Relancer/ })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Voir logs/ })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Contacter DBA/ })).toBeInTheDocument();
  });

  it('calls onRetry when Relancer is clicked', async () => {
    const onRetry = vi.fn();
    render(<StructuredErrorCard {...defaultProps} onRetry={onRetry} />);
    await userEvent.click(screen.getByRole('button', { name: /Relancer/ }));
    expect(onRetry).toHaveBeenCalledTimes(1);
  });

  it('calls onViewLogs when Voir logs is clicked', async () => {
    const onViewLogs = vi.fn();
    render(<StructuredErrorCard {...defaultProps} onViewLogs={onViewLogs} />);
    await userEvent.click(screen.getByRole('button', { name: /Voir logs/ }));
    expect(onViewLogs).toHaveBeenCalledTimes(1);
  });

  it('calls onContact when Contacter DBA is clicked', async () => {
    const onContact = vi.fn();
    render(<StructuredErrorCard {...defaultProps} onContact={onContact} />);
    await userEvent.click(screen.getByRole('button', { name: /Contacter DBA/ }));
    expect(onContact).toHaveBeenCalledTimes(1);
  });

  it('has aria-labelledby for sections (AC5)', () => {
    render(<StructuredErrorCard {...defaultProps} />);
    const alert = screen.getByRole('alert');
    const quoiSection = within(alert).getByText('Quoi').closest('section');
    const pourquoiSection = within(alert).getByText('Pourquoi').closest('section');
    expect(quoiSection).toHaveAttribute('aria-labelledby');
    expect(pourquoiSection).toHaveAttribute('aria-labelledby');
  });
});

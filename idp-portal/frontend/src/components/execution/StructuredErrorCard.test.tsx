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

  // Story 7.2: Business variant tests (Task 5.3)
  describe('Business Variant (Story 7.2)', () => {
    it('renders simplified labels in business variant', () => {
      render(<StructuredErrorCard {...defaultProps} variant="business" />);
      expect(screen.getByText("Qu'est-ce qui s'est passe?")).toBeInTheDocument();
      expect(screen.getByText('Explication')).toBeInTheDocument();
    });

    it('keeps default labels when variant is not specified', () => {
      render(<StructuredErrorCard {...defaultProps} />);
      expect(screen.getByText('Quoi')).toBeInTheDocument();
      expect(screen.getByText('Pourquoi')).toBeInTheDocument();
    });

    it('keeps default labels when variant is default', () => {
      render(<StructuredErrorCard {...defaultProps} variant="default" />);
      expect(screen.getByText('Quoi')).toBeInTheDocument();
      expect(screen.getByText('Pourquoi')).toBeInTheDocument();
    });

    it('sanitizes technical terms in error message for business variant', () => {
      const technicalError = 'Connection timeout on backend API endpoint after retry';
      render(
        <StructuredErrorCard
          quoi="Étape Platform a échoué"
          pourquoi={technicalError}
          variant="business"
        />
      );
      // Technical terms should be replaced with simpler ones
      // "backend" -> "systeme", "API" -> "interface", "endpoint" -> "point d'acces", "retry" -> "nouvel essai"
      expect(screen.getByText(/systeme/)).toBeInTheDocument();
      expect(screen.queryByText(/backend/)).not.toBeInTheDocument();
    });

    it('does not sanitize error message in default variant', () => {
      const technicalError = 'Connection timeout on backend API endpoint';
      render(
        <StructuredErrorCard
          quoi="Étape Platform a échoué"
          pourquoi={technicalError}
          variant="default"
        />
      );
      // Technical terms should remain
      expect(screen.getByText(/backend/)).toBeInTheDocument();
    });

    it('shows Contact DBA as primary button in business variant', () => {
      const onContact = vi.fn();
      render(
        <StructuredErrorCard {...defaultProps} onContact={onContact} variant="business" />
      );
      // In business variant, Contact DBA should be the primary button (first and type="primary")
      const buttons = screen.getAllByRole('button');
      expect(buttons[0]).toHaveTextContent('Contacter DBA');
    });

    it('shows Relancer as primary button in default variant', () => {
      const onRetry = vi.fn();
      render(
        <StructuredErrorCard {...defaultProps} onRetry={onRetry} variant="default" />
      );
      // In default variant, Relancer should be first
      const buttons = screen.getAllByRole('button');
      expect(buttons[0]).toHaveTextContent('Relancer');
    });

    it('shows Voir logs with reduced prominence in business variant', () => {
      const onViewLogs = vi.fn();
      render(
        <StructuredErrorCard {...defaultProps} onViewLogs={onViewLogs} variant="business" />
      );
      // Voir logs should be present but as text button (less prominent)
      const voirLogsButton = screen.getByRole('button', { name: /Voir logs/ });
      expect(voirLogsButton).toBeInTheDocument();
    });

    it('has aria-labelledby for sections in business variant', () => {
      render(<StructuredErrorCard {...defaultProps} variant="business" />);
      const alert = screen.getByRole('alert');
      const quoiSection = within(alert).getByText("Qu'est-ce qui s'est passe?").closest('section');
      const pourquoiSection = within(alert).getByText('Explication').closest('section');
      expect(quoiSection).toHaveAttribute('aria-labelledby');
      expect(pourquoiSection).toHaveAttribute('aria-labelledby');
    });
  });

  // Story 9.1: Remediation suggestions tests (Task 16)
  describe('Remediation Suggestions (Story 9.1)', () => {
    const mockSuggestions = [
      {
        action_id: 42,
        action_name: 'Fix Database Issue',
        action_description: 'Restarts the database listener',
        matching_rule: {
          error_pattern: 'ORA-\\d+',
          target_action_id: 42,
          environments: ['prod'],
          auto_trigger: false,
          risk_level: 'medium' as const,
        },
      },
      {
        action_id: 10,
        action_name: 'Retry Connection',
        action_description: null,
        matching_rule: {
          error_pattern: 'timeout',
          target_action_id: 10,
          environments: ['dev', 'prod'],
          auto_trigger: true,
          risk_level: 'low' as const,
        },
      },
    ];

    it('renders remediation suggestions section when suggestions provided', () => {
      render(
        <StructuredErrorCard
          {...defaultProps}
          remediationSuggestions={mockSuggestions}
        />
      );
      expect(screen.getByText('Actions correctives suggérées')).toBeInTheDocument();
      expect(screen.getByTestId('remediation-suggestions-section')).toBeInTheDocument();
    });

    it('renders suggestion buttons with action names', () => {
      render(
        <StructuredErrorCard
          {...defaultProps}
          remediationSuggestions={mockSuggestions}
        />
      );
      expect(screen.getByRole('button', { name: /Fix Database Issue/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /Retry Connection/i })).toBeInTheDocument();
    });

    it('does not render suggestions section when no suggestions', () => {
      render(<StructuredErrorCard {...defaultProps} />);
      expect(screen.queryByText('Actions correctives suggérées')).not.toBeInTheDocument();
      expect(screen.queryByTestId('remediation-suggestions-section')).not.toBeInTheDocument();
    });

    it('does not render suggestions section when empty array', () => {
      render(
        <StructuredErrorCard
          {...defaultProps}
          remediationSuggestions={[]}
        />
      );
      expect(screen.queryByText('Actions correctives suggérées')).not.toBeInTheDocument();
      expect(screen.queryByTestId('remediation-suggestions-section')).not.toBeInTheDocument();
    });

    it('calls onSuggestionClick when suggestion button is clicked', async () => {
      const onSuggestionClick = vi.fn();
      render(
        <StructuredErrorCard
          {...defaultProps}
          remediationSuggestions={mockSuggestions}
          onSuggestionClick={onSuggestionClick}
        />
      );
      await userEvent.click(screen.getByRole('button', { name: /Fix Database Issue/i }));
      expect(onSuggestionClick).toHaveBeenCalledTimes(1);
      expect(onSuggestionClick).toHaveBeenCalledWith(mockSuggestions[0]);
    });

    it('renders loading skeleton when suggestionsLoading is true', () => {
      render(
        <StructuredErrorCard
          {...defaultProps}
          suggestionsLoading={true}
        />
      );
      expect(screen.getByText('Actions correctives suggérées')).toBeInTheDocument();
      // Skeleton buttons are rendered
      expect(screen.queryByTestId('remediation-suggestions-section')).not.toBeInTheDocument();
    });

    it('does not render loading skeleton when not loading and no suggestions', () => {
      render(
        <StructuredErrorCard
          {...defaultProps}
          suggestionsLoading={false}
        />
      );
      expect(screen.queryByText('Actions correctives suggérées')).not.toBeInTheDocument();
    });

    it('first suggestion button has primary danger style', () => {
      render(
        <StructuredErrorCard
          {...defaultProps}
          remediationSuggestions={mockSuggestions}
        />
      );
      const firstButton = screen.getByTestId('remediation-suggestion-42');
      expect(firstButton).toHaveClass('ant-btn-primary');
      expect(firstButton).toHaveClass('ant-btn-dangerous');
    });

    it('suggestion buttons have accessible labels', () => {
      render(
        <StructuredErrorCard
          {...defaultProps}
          remediationSuggestions={mockSuggestions}
        />
      );
      expect(
        screen.getByRole('button', { name: /Exécuter action corrective: Fix Database Issue/i })
      ).toBeInTheDocument();
    });
  });
});

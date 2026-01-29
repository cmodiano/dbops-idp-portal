import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { ActionCard } from './ActionCard';
import type { ActionPreviewData } from '../../types/api';

const mockAction: ActionPreviewData = {
  name: 'Creer PDB Oracle',
  description: 'Cree une nouvelle Pluggable Database Oracle sur le serveur cible avec les parametres specifies.',
  category: 'Provisioning',
  engine: 'Oracle',
  platform: 'AAP',
  impact_level: 'medium',
  parameters_schema: null,
  tags: ['oracle', 'provisioning', 'database'],
};

describe('ActionCard', () => {
  it('renders action name and description', () => {
    render(<ActionCard action={mockAction} />);

    expect(screen.getByText('Creer PDB Oracle')).toBeInTheDocument();
    expect(screen.getByText(/Cree une nouvelle Pluggable Database/)).toBeInTheDocument();
  });

  it('renders with correct aria-label for accessibility (includes impact when present)', () => {
    render(<ActionCard action={mockAction} />);

    const card = screen.getByRole('article');
    expect(card).toHaveAttribute('aria-label', 'Action: Creer PDB Oracle, impact Moyen');
  });

  it('renders aria-label without impact when impact_level is null', () => {
    const actionWithoutImpact = { ...mockAction, impact_level: null };
    render(<ActionCard action={actionWithoutImpact} />);

    const card = screen.getByRole('article');
    expect(card).toHaveAttribute('aria-label', 'Action: Creer PDB Oracle');
  });

  it('renders impact indicator when impact_level is provided', () => {
    render(<ActionCard action={mockAction} />);

    expect(screen.getByText('Moyen')).toBeInTheDocument();
  });

  it('does not render impact indicator when impact_level is null', () => {
    const actionWithoutImpact = { ...mockAction, impact_level: null };
    render(<ActionCard action={actionWithoutImpact} />);

    expect(screen.queryByText('Moyen')).not.toBeInTheDocument();
  });

  it('renders tags up to MAX_VISIBLE_TAGS', () => {
    render(<ActionCard action={mockAction} />);

    expect(screen.getByText('oracle')).toBeInTheDocument();
    expect(screen.getByText('provisioning')).toBeInTheDocument();
    expect(screen.getByText('database')).toBeInTheDocument();
  });

  it('shows +N indicator when tags exceed MAX_VISIBLE_TAGS', () => {
    const actionWithManyTags = {
      ...mockAction,
      tags: ['oracle', 'provisioning', 'database', 'extra1', 'extra2'],
    };
    render(<ActionCard action={actionWithManyTags} />);

    expect(screen.getByText('+2')).toBeInTheDocument();
  });

  it('renders category badge', () => {
    render(<ActionCard action={mockAction} />);

    expect(screen.getByText('Provisioning')).toBeInTheDocument();
  });

  it('calls onClick when clicked with default variant', () => {
    const handleClick = vi.fn();
    render(<ActionCard action={mockAction} onClick={handleClick} variant="default" />);

    const card = screen.getByRole('article');
    fireEvent.click(card);

    expect(handleClick).toHaveBeenCalledTimes(1);
  });

  it('does not call onClick when clicked with preview variant', () => {
    const handleClick = vi.fn();
    render(<ActionCard action={mockAction} onClick={handleClick} variant="preview" />);

    const card = screen.getByRole('article');
    fireEvent.click(card);

    expect(handleClick).not.toHaveBeenCalled();
  });

  it('is keyboard accessible - activates on Enter key', () => {
    const handleClick = vi.fn();
    render(<ActionCard action={mockAction} onClick={handleClick} />);

    const card = screen.getByRole('article');
    fireEvent.keyDown(card, { key: 'Enter' });

    expect(handleClick).toHaveBeenCalledTimes(1);
  });

  it('is keyboard accessible - activates on Space key', () => {
    const handleClick = vi.fn();
    render(<ActionCard action={mockAction} onClick={handleClick} />);

    const card = screen.getByRole('article');
    fireEvent.keyDown(card, { key: ' ' });

    expect(handleClick).toHaveBeenCalledTimes(1);
  });

  it('renders placeholder text when name is empty', () => {
    const actionWithoutName = { ...mockAction, name: '' };
    render(<ActionCard action={actionWithoutName} />);

    expect(screen.getByText('Sans nom')).toBeInTheDocument();
  });

  it('renders placeholder text when description is null', () => {
    const actionWithoutDesc = { ...mockAction, description: null };
    render(<ActionCard action={actionWithoutDesc} />);

    expect(screen.getByText('Aucune description')).toBeInTheDocument();
  });

  it('is not focusable in preview variant', () => {
    render(<ActionCard action={mockAction} variant="preview" />);

    const card = screen.getByRole('article');
    expect(card).not.toHaveAttribute('tabIndex');
  });

  it('is focusable when onClick is provided with default variant', () => {
    const handleClick = vi.fn();
    render(<ActionCard action={mockAction} onClick={handleClick} variant="default" />);

    const card = screen.getByRole('article');
    expect(card).toHaveAttribute('tabIndex', '0');
  });

  it('renders execution_count when available (Task 1.1)', () => {
    const actionWithCount = { ...mockAction, execution_count: 42 };
    render(<ActionCard action={actionWithCount} />);

    expect(screen.getByText('42 exécutions')).toBeInTheDocument();
  });

  it('renders singular "exécution" when execution_count is 1', () => {
    const actionWithOne = { ...mockAction, execution_count: 1 };
    render(<ActionCard action={actionWithOne} />);

    expect(screen.getByText('1 exécution')).toBeInTheDocument();
  });

  it('does not render execution_count when undefined or null', () => {
    render(<ActionCard action={mockAction} />);

    expect(screen.queryByText(/exécution/)).not.toBeInTheDocument();
  });
});

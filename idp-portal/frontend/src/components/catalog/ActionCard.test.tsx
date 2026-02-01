import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { ThemeProvider } from '../../contexts/ThemeContext';
import { ActionCard } from './ActionCard';
import type { ActionPreviewData } from '../../types/api';

const mockAction: ActionPreviewData = {
  name: 'Creer PDB Oracle',
  description: 'Cree une nouvelle Pluggable Database Oracle sur le serveur cible avec les parametres specifies.',
  engine: 'Oracle',
  platform: 'AAP',
  impact_level: 'medium',
  parameters_schema: null,
  tags: ['oracle', 'provisioning', 'database'],
};

function renderWithTheme(ui: React.ReactElement) {
  return render(<ThemeProvider>{ui}</ThemeProvider>);
}

describe('ActionCard', () => {
  beforeEach(() => {
    window.matchMedia = vi.fn().mockImplementation((query: string) => ({
      matches: query.includes('dark') ? false : true,
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    }));
  });

  it('renders action name and description', () => {
    renderWithTheme(<ActionCard action={mockAction} />);

    expect(screen.getByText('Creer PDB Oracle')).toBeInTheDocument();
    expect(screen.getByText(/Cree une nouvelle Pluggable Database/)).toBeInTheDocument();
  });

  it('renders with correct aria-label for accessibility (includes impact when present)', () => {
    renderWithTheme(<ActionCard action={mockAction} />);

    const card = screen.getByRole('article');
    expect(card).toHaveAttribute('aria-label', 'Action: Creer PDB Oracle, impact Moyen');
  });

  it('renders aria-label without impact when impact_level is null', () => {
    const actionWithoutImpact = { ...mockAction, impact_level: null };
    renderWithTheme(<ActionCard action={actionWithoutImpact} />);

    const card = screen.getByRole('article');
    expect(card).toHaveAttribute('aria-label', 'Action: Creer PDB Oracle');
  });

  it('renders impact indicator when impact_level is provided', () => {
    renderWithTheme(<ActionCard action={mockAction} />);

    expect(screen.getByText('Moyen')).toBeInTheDocument();
  });

  it('does not render impact indicator when impact_level is null', () => {
    const actionWithoutImpact = { ...mockAction, impact_level: null };
    renderWithTheme(<ActionCard action={actionWithoutImpact} />);

    expect(screen.queryByText('Moyen')).not.toBeInTheDocument();
  });

  it('renders tags up to MAX_VISIBLE_TAGS', () => {
    renderWithTheme(<ActionCard action={mockAction} />);

    expect(screen.getByText('oracle')).toBeInTheDocument();
    expect(screen.getByText('provisioning')).toBeInTheDocument();
    expect(screen.getByText('database')).toBeInTheDocument();
  });

  it('shows +N indicator when tags exceed MAX_VISIBLE_TAGS', () => {
    const actionWithManyTags = {
      ...mockAction,
      tags: ['oracle', 'provisioning', 'database', 'extra1', 'extra2'],
    };
    renderWithTheme(<ActionCard action={actionWithManyTags} />);

    expect(screen.getByText('+2')).toBeInTheDocument();
  });

  it('calls onClick when clicked with default variant', () => {
    const handleClick = vi.fn();
    renderWithTheme(<ActionCard action={mockAction} onClick={handleClick} variant="default" />);

    const card = screen.getByRole('article');
    fireEvent.click(card);

    expect(handleClick).toHaveBeenCalledTimes(1);
  });

  it('does not call onClick when clicked with preview variant', () => {
    const handleClick = vi.fn();
    renderWithTheme(<ActionCard action={mockAction} onClick={handleClick} variant="preview" />);

    const card = screen.getByRole('article');
    fireEvent.click(card);

    expect(handleClick).not.toHaveBeenCalled();
  });

  it('is keyboard accessible - activates on Enter key', () => {
    const handleClick = vi.fn();
    renderWithTheme(<ActionCard action={mockAction} onClick={handleClick} />);

    const card = screen.getByRole('article');
    fireEvent.keyDown(card, { key: 'Enter' });

    expect(handleClick).toHaveBeenCalledTimes(1);
  });

  it('is keyboard accessible - activates on Space key', () => {
    const handleClick = vi.fn();
    renderWithTheme(<ActionCard action={mockAction} onClick={handleClick} />);

    const card = screen.getByRole('article');
    fireEvent.keyDown(card, { key: ' ' });

    expect(handleClick).toHaveBeenCalledTimes(1);
  });

  it('renders placeholder text when name is empty', () => {
    const actionWithoutName = { ...mockAction, name: '' };
    renderWithTheme(<ActionCard action={actionWithoutName} />);

    expect(screen.getByText('Sans nom')).toBeInTheDocument();
  });

  it('renders placeholder text when description is null', () => {
    const actionWithoutDesc = { ...mockAction, description: null };
    renderWithTheme(<ActionCard action={actionWithoutDesc} />);

    expect(screen.getByText('Aucune description')).toBeInTheDocument();
  });

  it('is not focusable in preview variant', () => {
    renderWithTheme(<ActionCard action={mockAction} variant="preview" />);

    const card = screen.getByRole('article');
    expect(card).not.toHaveAttribute('tabIndex');
  });

  it('is focusable when onClick is provided with default variant', () => {
    const handleClick = vi.fn();
    renderWithTheme(<ActionCard action={mockAction} onClick={handleClick} variant="default" />);

    const card = screen.getByRole('article');
    expect(card).toHaveAttribute('tabIndex', '0');
  });

  it('renders execution_count when available (Task 1.1)', () => {
    const actionWithCount = { ...mockAction, execution_count: 42 };
    renderWithTheme(<ActionCard action={actionWithCount} />);

    expect(screen.getByText('42 exécutions')).toBeInTheDocument();
  });

  it('renders singular "exécution" when execution_count is 1', () => {
    const actionWithOne = { ...mockAction, execution_count: 1 };
    renderWithTheme(<ActionCard action={actionWithOne} />);

    expect(screen.getByText('1 exécution')).toBeInTheDocument();
  });

  it('does not render execution_count when undefined or null', () => {
    renderWithTheme(<ActionCard action={mockAction} />);

    expect(screen.queryByText(/exécution/)).not.toBeInTheDocument();
  });
});

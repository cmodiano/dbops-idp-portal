/**
 * Tests for ActionPalette component (Story 55.5, Tâche 8).
 * Cible : ≥ 90 % de couverture sur ActionPalette.tsx (56.2 → 90 %).
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ActionPalette } from './ActionPalette';
import type { ActionListItem } from '../../types/api';

vi.mock('../../hooks/useEligibleActions', () => ({
  useEligibleActions: vi.fn(),
}));

import { useEligibleActions } from '../../hooks/useEligibleActions';

const mockActions: ActionListItem[] = [
  { id: 1, name: 'Deploy App', engine: 'Ansible', status: 'published', created_at: '', execution_count: 0 },
  { id: 2, name: 'Backup DB', engine: 'Oracle', status: 'published', created_at: '', execution_count: 0 },
  { id: 3, name: 'Patch Server', engine: 'Ansible', status: 'published', created_at: '', execution_count: 0 },
];

function mockUseEligibleActions(overrides = {}) {
  vi.mocked(useEligibleActions).mockReturnValue({
    eligibleActions: mockActions,
    loadingActions: false,
    loadError: null,
    ...overrides,
  });
}

describe('ActionPalette', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUseEligibleActions();
  });

  it('affiche le titre de la section actions plateforme', () => {
    render(<ActionPalette />);
    // Story 57.13: section renamed to "Actions (Exécuter)"
    expect(screen.getByText('Actions (Exécuter)')).toBeInTheDocument();
  });

  it('affiche toutes les actions', () => {
    render(<ActionPalette />);
    expect(screen.getByText('Deploy App')).toBeInTheDocument();
    expect(screen.getByText('Backup DB')).toBeInTheDocument();
    expect(screen.getByText('Patch Server')).toBeInTheDocument();
  });

  it('affiche le moteur de chaque action', () => {
    render(<ActionPalette />);
    const ansibleLabels = screen.getAllByText('Ansible');
    expect(ansibleLabels.length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('Oracle')).toBeInTheDocument();
  });

  it('affiche un Spin quand loadingActions=true', () => {
    mockUseEligibleActions({ eligibleActions: [], loadingActions: true });
    render(<ActionPalette />);
    expect(document.querySelector('.ant-spin')).toBeInTheDocument();
  });

  it('affiche une Alert quand loadError est défini', () => {
    mockUseEligibleActions({ eligibleActions: [], loadError: 'Erreur de chargement' });
    render(<ActionPalette />);
    expect(document.querySelector('.ant-alert')).toBeInTheDocument();
  });

  it('affiche "Aucune action disponible" quand la liste est vide', () => {
    mockUseEligibleActions({ eligibleActions: [] });
    render(<ActionPalette />);
    expect(screen.getByText('Aucune action disponible')).toBeInTheDocument();
  });

  it('filtre les actions par recherche sur le nom', async () => {
    const user = userEvent.setup();
    render(<ActionPalette />);

    const searchInput = screen.getByLabelText('Rechercher une action');
    await user.type(searchInput, 'Deploy');

    expect(screen.getByText('Deploy App')).toBeInTheDocument();
    expect(screen.queryByText('Backup DB')).not.toBeInTheDocument();
    expect(screen.queryByText('Patch Server')).not.toBeInTheDocument();
  });

  it('filtre les actions par recherche sur le moteur', async () => {
    const user = userEvent.setup();
    render(<ActionPalette />);

    const searchInput = screen.getByLabelText('Rechercher une action');
    await user.type(searchInput, 'Oracle');

    expect(screen.getByText('Backup DB')).toBeInTheDocument();
    expect(screen.queryByText('Deploy App')).not.toBeInTheDocument();
  });

  it('affiche toutes les actions quand la recherche est effacée', async () => {
    const user = userEvent.setup();
    render(<ActionPalette />);

    const searchInput = screen.getByLabelText('Rechercher une action');
    await user.type(searchInput, 'Deploy');
    await user.clear(searchInput);

    expect(screen.getByText('Deploy App')).toBeInTheDocument();
    expect(screen.getByText('Backup DB')).toBeInTheDocument();
  });

  it('les actions sont draggable quand disabled=false', () => {
    render(<ActionPalette disabled={false} />);
    // Vérifier que les divs d'action ont draggable=true
    const draggableItems = document.querySelectorAll('[draggable="true"]');
    expect(draggableItems.length).toBeGreaterThan(0);
  });

  it('les actions ne sont pas draggable quand disabled=true', () => {
    render(<ActionPalette disabled={true} />);
    const draggableItems = document.querySelectorAll('[draggable="true"]');
    expect(draggableItems.length).toBe(0);
  });

  it('déclenche dragstart avec les données de l\'action', () => {
    render(<ActionPalette />);
    const deployCard = screen.getByText('Deploy App').closest('div[draggable]');
    expect(deployCard).toBeTruthy();

    const setData = vi.fn();
    fireEvent.dragStart(deployCard!, {
      dataTransfer: { setData, effectAllowed: '' },
    });

    expect(setData).toHaveBeenCalledWith('application/workflow-action', expect.stringContaining('Deploy App'));
  });

  it('n\'appelle pas setData quand disabled=true lors du drag', () => {
    render(<ActionPalette disabled={true} />);
    // Avec disabled=true, les divs n'ont pas draggable=true
    const draggableItems = document.querySelectorAll('[draggable="true"]');
    expect(draggableItems.length).toBe(0);
  });

  it('affiche le champ de recherche désactivé quand disabled=true', () => {
    render(<ActionPalette disabled={true} />);
    const searchInput = screen.getByLabelText('Rechercher une action');
    expect(searchInput).toBeDisabled();
  });

  // Story 57.16: schedule_execution bouton
  it('affiche le bouton "Planifier une exécution" (schedule_execution) dans les steps spéciaux', () => {
    render(<ActionPalette />);
    expect(screen.getByText('Planifier une exécution')).toBeInTheDocument();
  });

  it('le bouton schedule_execution appelle onAddSpecialStep avec le bon type', () => {
    const onAddSpecialStep = vi.fn();
    render(<ActionPalette onAddSpecialStep={onAddSpecialStep} />);
    const btn = screen.getByTestId('add-special-step-schedule_execution');
    fireEvent.click(btn);
    expect(onAddSpecialStep).toHaveBeenCalledWith('schedule_execution');
  });

});

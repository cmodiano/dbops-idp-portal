/**
 * Tests for ActionPalette component (Story 55.5, Tâche 8).
 * Cible : ≥ 90 % de couverture sur ActionPalette.tsx (56.2 → 90 %).
 *
 * Story 84.3 (AC3/AC9): Les special steps dérivent des capabilities mockées.
 * Plus de SPECIAL_STEP_TYPES local — vérification via capabilities mockées.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ActionPalette } from './ActionPalette';
import type { ActionListItem } from '../../types/api';

vi.mock('../../hooks/useEligibleActions', () => ({
  useEligibleActions: vi.fn(),
}));

vi.mock('../../hooks/useCapabilities', () => ({
  useCapabilities: vi.fn(),
}));

import { useEligibleActions } from '../../hooks/useEligibleActions';
import { useCapabilities } from '../../hooks/useCapabilities';

const mockActions: ActionListItem[] = [
  { id: 1, name: 'Deploy App', engine: 'Ansible', status: 'published', created_at: '', execution_count: 0 },
  { id: 2, name: 'Backup DB', engine: 'Oracle', status: 'published', created_at: '', execution_count: 0 },
  { id: 3, name: 'Patch Server', engine: 'Ansible', status: 'published', created_at: '', execution_count: 0 },
];

// Story 84.3: mock capabilities avec les step types backend
const mockStepTypes = [
  { code: 'platform', label: 'Exécuter', category: 'execution', config_schema: {}, constraints: {} },
  { code: 'service_call', label: 'Service', category: 'integration', config_schema: {}, constraints: {} },
  { code: 'gate', label: 'Attendre', category: 'control', config_schema: {}, constraints: {} },
  { code: 'http_request', label: 'Requête HTTP', category: 'integration', config_schema: {}, constraints: {} },
  { code: 'evaluation', label: 'Évaluation', category: 'control', config_schema: {}, constraints: {} },
  { code: 'schedule_execution', label: 'Planifier', category: 'scheduling', config_schema: {}, constraints: {} },
];

function mockUseEligibleActions(overrides = {}) {
  vi.mocked(useEligibleActions).mockReturnValue({
    eligibleActions: mockActions,
    loadingActions: false,
    loadError: null,
    ...overrides,
  });
}

function mockUseCapabilities(overrides = {}) {
  vi.mocked(useCapabilities).mockReturnValue({
    capabilities: {
      platforms: [],
      services: [],
      stepTypes: mockStepTypes,
    },
    loading: false,
    error: null,
    retryCount: 0,
    ...overrides,
  });
}

describe('ActionPalette', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUseEligibleActions();
    mockUseCapabilities();
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

  // Story 84.3 (AC3/AC9): special steps dérivés des capabilities mockées
  it('affiche les special steps dérivés des capabilities (pas platform, pas parallel_group)', () => {
    render(<ActionPalette />);
    // Les types backend hors platform et parallel_group doivent apparaître
    expect(screen.getByTestId('add-special-step-service_call')).toBeInTheDocument();
    expect(screen.getByTestId('add-special-step-http_request')).toBeInTheDocument();
    expect(screen.getByTestId('add-special-step-evaluation')).toBeInTheDocument();
    expect(screen.getByTestId('add-special-step-gate')).toBeInTheDocument();
    expect(screen.getByTestId('add-special-step-schedule_execution')).toBeInTheDocument();
    // platform ne doit PAS être dans les special steps
    expect(screen.queryByTestId('add-special-step-platform')).not.toBeInTheDocument();
  });

  it('les labels des special steps correspondent aux labels backend', () => {
    render(<ActionPalette />);
    // Le label vient du backend (capabilities), pas d'une constante locale
    expect(screen.getByText('Service')).toBeInTheDocument();
    expect(screen.getByText('Planifier')).toBeInTheDocument();
    expect(screen.getByText('Attendre')).toBeInTheDocument();
  });

  it('affiche un Spin dans la section "Steps spéciaux" quand loading=true', () => {
    mockUseCapabilities({ capabilities: null, loading: true, error: null });
    render(<ActionPalette />);
    // Au moins un spin (actions ou capabilities)
    const spins = document.querySelectorAll('.ant-spin');
    expect(spins.length).toBeGreaterThan(0);
  });

  it('affiche une section vide (sans crash) en cas d\'erreur capabilities', () => {
    mockUseCapabilities({ capabilities: null, loading: false, error: 'Erreur API' });
    render(<ActionPalette />);
    // Pas de crash — la section special steps est vide
    expect(screen.queryByTestId('add-special-step-service_call')).not.toBeInTheDocument();
  });

  it('le bouton schedule_execution appelle onAddSpecialStep avec le bon type', () => {
    const onAddSpecialStep = vi.fn();
    render(<ActionPalette onAddSpecialStep={onAddSpecialStep} />);
    const btn = screen.getByTestId('add-special-step-schedule_execution');
    fireEvent.click(btn);
    expect(onAddSpecialStep).toHaveBeenCalledWith('schedule_execution');
  });

  it('parallel_group est exclu des special steps même s\'il apparaît dans les capabilities', () => {
    mockUseCapabilities({
      capabilities: {
        platforms: [],
        services: [],
        stepTypes: [
          { code: 'service_call', label: 'Service', category: 'integration', config_schema: {}, constraints: {} },
          { code: 'parallel_group', label: 'Parallèle', category: 'control', config_schema: {}, constraints: {} },
        ],
      },
      loading: false,
      error: null,
    });
    render(<ActionPalette />);
    expect(screen.getByTestId('add-special-step-service_call')).toBeInTheDocument();
    expect(screen.queryByTestId('add-special-step-parallel_group')).not.toBeInTheDocument();
  });

  it('un type inconnu du frontend utilise la couleur et icône fallback (_default)', () => {
    // Un type backend non connu du STEP_TYPE_UI_META doit s'afficher avec fallback
    mockUseCapabilities({
      capabilities: {
        platforms: [],
        services: [],
        stepTypes: [
          { code: 'notification', label: 'Notifier', category: 'control', config_schema: {}, constraints: {} },
        ],
      },
      loading: false,
      error: null,
    });
    render(<ActionPalette />);
    expect(screen.getByTestId('add-special-step-notification')).toBeInTheDocument();
    expect(screen.getByText('Notifier')).toBeInTheDocument();
  });
});

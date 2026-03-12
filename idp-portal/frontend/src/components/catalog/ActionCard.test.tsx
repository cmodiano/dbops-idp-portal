import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
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

  // Story 5.7 / 20.6: Workflow icon and label tests
  describe('workflow display (Story 5.7, AC3)', () => {
    const workflowAction: ActionPreviewData = {
      ...mockAction,
      item_type: 'workflow',
    };

    it('renders aria-label with "Workflow:" prefix for workflow item_type', () => {
      renderWithTheme(<ActionCard action={workflowAction} />);

      const card = screen.getByRole('article');
      expect(card).toHaveAttribute('aria-label', 'Workflow: Creer PDB Oracle, impact Moyen');
    });

    it('renders workflow icon (WorkflowIcon) instead of engine icon', () => {
      const { container } = renderWithTheme(<ActionCard action={workflowAction} />);

      expect(container.querySelector('svg')).toBeInTheDocument();
    });

    it('renders standard engine icon when item_type is not workflow', () => {
      renderWithTheme(<ActionCard action={mockAction} />);

      const card = screen.getByRole('article');
      expect(card).toHaveAttribute('aria-label', 'Action: Creer PDB Oracle, impact Moyen');
    });
  });

  // Story 46.1: affordance — CTA, badge "Incomplet"
  describe('Story 46.1 — affordance', () => {
    it('affiche le CTA "Voir les détails" quand onClick fourni, variant default', () => {
      const handleClick = vi.fn();
      renderWithTheme(<ActionCard action={mockAction} onClick={handleClick} variant="default" />);

      expect(screen.getByRole('button', { name: /Voir les détails de Creer PDB Oracle/ })).toBeInTheDocument();
      expect(screen.getByText('Voir les détails')).toBeInTheDocument();
    });

    it('affiche le CTA "Exécuter" quand onClick fourni, variant business', () => {
      const handleClick = vi.fn();
      renderWithTheme(<ActionCard action={mockAction} onClick={handleClick} variant="business" />);

      expect(screen.getByRole('button', { name: /Exécuter Creer PDB Oracle/ })).toBeInTheDocument();
      expect(screen.getByText('Exécuter')).toBeInTheDocument();
    });

    it('n\'affiche pas le CTA en variant preview', () => {
      const handleClick = vi.fn();
      renderWithTheme(<ActionCard action={mockAction} onClick={handleClick} variant="preview" />);

      expect(screen.queryByText('Voir les détails')).not.toBeInTheDocument();
      expect(screen.queryByText('Exécuter')).not.toBeInTheDocument();
    });

    it('affiche le badge "Incomplet" quand description null ET tags vide', () => {
      const incompleteAction = { ...mockAction, description: null, tags: [] };
      renderWithTheme(<ActionCard action={incompleteAction} onClick={vi.fn()} />);

      expect(screen.getByText('Incomplet')).toBeInTheDocument();
    });

    it('n\'affiche pas le badge "Incomplet" quand description présente', () => {
      renderWithTheme(<ActionCard action={mockAction} onClick={vi.fn()} />);

      expect(screen.queryByText('Incomplet')).not.toBeInTheDocument();
    });

    it('n\'affiche pas le badge "Incomplet" quand tags présents (même sans description)', () => {
      const actionWithTagsNoDesc = { ...mockAction, description: null, tags: ['oracle'] };
      renderWithTheme(<ActionCard action={actionWithTagsNoDesc} onClick={vi.fn()} />);

      expect(screen.queryByText('Incomplet')).not.toBeInTheDocument();
    });

    it('n\'affiche pas le badge "Incomplet" en variant preview', () => {
      const incompleteAction = { ...mockAction, description: null, tags: [] };
      renderWithTheme(<ActionCard action={incompleteAction} variant="preview" />);

      expect(screen.queryByText('Incomplet')).not.toBeInTheDocument();
    });

    it('le CTA a un aria-label explicite', () => {
      const handleClick = vi.fn();
      renderWithTheme(<ActionCard action={mockAction} onClick={handleClick} variant="default" />);

      const ctaButton = screen.getByRole('button', { name: /Voir les détails de Creer PDB Oracle/ });
      expect(ctaButton).toHaveAttribute('aria-label', 'Voir les détails de Creer PDB Oracle');
    });

    it('cliquer le CTA appelle onClick exactement 1 fois (stopPropagation empêche double-déclenchement)', () => {
      const handleClick = vi.fn();
      renderWithTheme(<ActionCard action={mockAction} onClick={handleClick} variant="default" />);

      const ctaButton = screen.getByRole('button', { name: /Voir les détails de Creer PDB Oracle/ });
      fireEvent.click(ctaButton);

      expect(handleClick).toHaveBeenCalledTimes(1);
    });

    it('keyDown Enter sur le CTA appelle onClick exactement 1 fois (stopPropagation empêche double-déclenchement)', async () => {
      const handleClick = vi.fn();
      const user = userEvent.setup();
      renderWithTheme(<ActionCard action={mockAction} onClick={handleClick} variant="default" />);

      const ctaButton = screen.getByRole('button', { name: /Voir les détails de Creer PDB Oracle/ });
      ctaButton.focus();
      await user.keyboard('{Enter}');

      expect(handleClick).toHaveBeenCalledTimes(1);
    });

    it('affiche le CTA désactivé quand aucun onClick fourni (AC 2: désactivé, pas absent)', () => {
      renderWithTheme(<ActionCard action={mockAction} variant="default" />);

      const ctaButton = screen.getByRole('button', { name: /Voir les détails/ });
      expect(ctaButton).toBeDisabled();
    });

    it('affiche le badge "Incomplet" quand tags est null (pas de tags du tout)', () => {
      // Double cast: simule une API retournant null au lieu de [] ; bypass TypeScript pour ce test edge-case
      const incompleteAction = { ...mockAction, description: null, tags: null as unknown as string[] };
      renderWithTheme(<ActionCard action={incompleteAction} onClick={vi.fn()} />);

      expect(screen.getByText('Incomplet')).toBeInTheDocument();
    });
  });

  // Story 69.2: Technology icons and workflow indicator tests
  describe('Story 69.2 — technology icons and workflow indicator', () => {
    const workflowWithTechs: ActionPreviewData = {
      ...mockAction,
      item_type: 'workflow',
      technologies: ['Oracle', 'SQL Server'],
    };

    const workflowManyTechs: ActionPreviewData = {
      ...mockAction,
      item_type: 'workflow',
      technologies: ['Oracle', 'SQL Server', 'DB2', 'MySQL'],
    };

    const workflowNoTechs: ActionPreviewData = {
      ...mockAction,
      item_type: 'workflow',
    };

    const workflowEmptyTechs: ActionPreviewData = {
      ...mockAction,
      item_type: 'workflow',
      technologies: [''],
    };

    const simpleAction: ActionPreviewData = {
      ...mockAction,
      item_type: 'action',
      engine: 'Oracle',
    };

    it('workflow displays technology icons when technologies present', () => {
      const { container } = renderWithTheme(<ActionCard action={workflowWithTechs} />);

      const techIcons = container.querySelector('[data-testid="technology-icons"]');
      expect(techIcons).toBeInTheDocument();
    });

    it('workflow shows overflow indicator when > maxVisible (2) technologies', () => {
      renderWithTheme(<ActionCard action={workflowManyTechs} />);

      expect(screen.getByTestId('technology-overflow')).toHaveTextContent('+2');
    });

    it('workflow with exactly 2 technologies shows no overflow indicator (boundary)', () => {
      const workflowExact2: ActionPreviewData = {
        ...mockAction,
        item_type: 'workflow',
        technologies: ['Oracle', 'SQL Server'],
      };
      renderWithTheme(<ActionCard action={workflowExact2} />);

      expect(screen.getByTestId('technology-icons')).toBeInTheDocument();
      expect(screen.queryByTestId('technology-overflow')).not.toBeInTheDocument();
    });

    it('workflow with technologies shows technology icons (no separate workflow indicator)', () => {
      renderWithTheme(<ActionCard action={workflowWithTechs} />);

      expect(screen.getByTestId('technology-icons')).toBeInTheDocument();
    });

    it('simple action has no workflow indicator', () => {
      renderWithTheme(<ActionCard action={simpleAction} />);

      expect(screen.queryByTestId('workflow-indicator')).not.toBeInTheDocument();
    });

    it('simple action displays single technology icon unchanged', () => {
      const { container } = renderWithTheme(<ActionCard action={simpleAction} />);

      // Should NOT have multi-tech icons container
      expect(container.querySelector('[data-testid="technology-icons"]')).not.toBeInTheDocument();
      // Should have engine icon (img or ant icon)
      expect(container.querySelector('.engine-icon-img') || container.querySelector('[aria-label^="Type: Action"]')).toBeTruthy();
    });

    it('workflow falls back to workflow icon when technologies field is absent', () => {
      const { container } = renderWithTheme(<ActionCard action={workflowNoTechs} />);

      // No multi-tech icons
      expect(container.querySelector('[data-testid="technology-icons"]')).not.toBeInTheDocument();
      // Should render a workflow SVG icon (from getItemTypeIcon)
      expect(container.querySelector('svg')).toBeInTheDocument();
    });

    it('workflow falls back to workflow icon when technologies is empty strings only', () => {
      const { container } = renderWithTheme(<ActionCard action={workflowEmptyTechs} />);

      expect(container.querySelector('[data-testid="technology-icons"]')).not.toBeInTheDocument();
      expect(container.querySelector('svg')).toBeInTheDocument();
    });
  });

  // Story 69.3: Included actions summary tests
  describe('Story 69.3 — included actions summary', () => {
    const workflowWith2Actions: ActionPreviewData = {
      ...mockAction,
      item_type: 'workflow',
      included_actions: [
        { id: 1, name: 'Backup', engine: 'oracle' },
        { id: 2, name: 'Deploy', engine: 'sqlserver' },
      ],
    };

    const workflowWith4Actions: ActionPreviewData = {
      ...mockAction,
      item_type: 'workflow',
      included_actions: [
        { id: 1, name: 'Backup', engine: 'oracle' },
        { id: 2, name: 'Deploy', engine: 'sqlserver' },
        { id: 3, name: 'Validate', engine: 'db2' },
        { id: 4, name: 'Cleanup', engine: null },
      ],
    };

    const simpleAction: ActionPreviewData = {
      ...mockAction,
      item_type: 'action',
      engine: 'Oracle',
    };

    const workflowEmptyActions: ActionPreviewData = {
      ...mockAction,
      item_type: 'workflow',
      included_actions: [],
    };

    const workflowNoActionsField: ActionPreviewData = {
      ...mockAction,
      item_type: 'workflow',
    };

    const workflowWith1Action: ActionPreviewData = {
      ...mockAction,
      item_type: 'workflow',
      included_actions: [
        { id: 1, name: 'Backup', engine: 'oracle' },
      ],
    };

    it('workflow displays included actions as chips with "Actions incluses" label', () => {
      renderWithTheme(<ActionCard action={workflowWith2Actions} />);

      const summary = screen.getByTestId('included-actions-summary');
      expect(summary).toBeInTheDocument();
      expect(screen.getByText('Actions incluses')).toBeInTheDocument();
      expect(screen.getByText(/Backup/)).toBeInTheDocument();
      expect(screen.getByText(/Deploy/)).toBeInTheDocument();
      // Boundary: exactly maxVisible actions = no overflow
      expect(screen.queryByText(/^\+/)).not.toBeInTheDocument();
    });

    it('workflow shows overflow indicator "+N" when > maxVisible actions', () => {
      renderWithTheme(<ActionCard action={workflowWith4Actions} />);

      const summary = screen.getByTestId('included-actions-summary');
      expect(summary).toBeInTheDocument();
      expect(screen.getByText(/Backup/)).toBeInTheDocument();
      expect(screen.getByText(/Deploy/)).toBeInTheDocument();
      expect(screen.getByText(/Validate/)).toBeInTheDocument();
      expect(screen.getByText('+1')).toBeInTheDocument();
    });

    it('simple action has no included actions summary', () => {
      renderWithTheme(<ActionCard action={simpleAction} />);

      expect(screen.queryByTestId('included-actions-summary')).not.toBeInTheDocument();
    });

    it('workflow with empty included_actions has no summary', () => {
      renderWithTheme(<ActionCard action={workflowEmptyActions} />);

      expect(screen.queryByTestId('included-actions-summary')).not.toBeInTheDocument();
    });

    it('workflow without included_actions field has no summary', () => {
      renderWithTheme(<ActionCard action={workflowNoActionsField} />);

      expect(screen.queryByTestId('included-actions-summary')).not.toBeInTheDocument();
    });

    it('workflow with single action shows it without overflow', () => {
      renderWithTheme(<ActionCard action={workflowWith1Action} />);

      const summary = screen.getByTestId('included-actions-summary');
      expect(summary).toBeInTheDocument();
      expect(screen.getByText(/Backup/)).toBeInTheDocument();
      expect(screen.queryByText(/autre/)).not.toBeInTheDocument();
    });

    it('included actions summary has aria-label for accessibility', () => {
      renderWithTheme(<ActionCard action={workflowWith2Actions} />);

      const summary = screen.getByTestId('included-actions-summary');
      expect(summary).toHaveAttribute('aria-label', 'Actions incluses dans le workflow');
    });

    it('action with null engine shows name without icon', () => {
      const workflowNullEngine: ActionPreviewData = {
        ...mockAction,
        item_type: 'workflow',
        included_actions: [
          { id: 1, name: 'Generic Task', engine: null },
        ],
      };
      renderWithTheme(<ActionCard action={workflowNullEngine} />);

      const summary = screen.getByTestId('included-actions-summary');
      expect(summary).toBeInTheDocument();
      expect(screen.getByText(/Generic Task/)).toBeInTheDocument();
    });
  });

  // Story 7.1: Business variant tests
  describe('business variant (Story 7.1)', () => {
    const actionWithTechnicalTerms: ActionPreviewData = {
      name: 'Database Action', // Name is not sanitized, only description
      description: 'Run the Ansible playbook to deploy the database via the pipeline',
      engine: 'Oracle',
      platform: 'AAP',
      impact_level: 'medium',
      parameters_schema: null,
      tags: ['provisioning'],
    };

    it('sanitizes technical terms in description for business variant', () => {
      renderWithTheme(<ActionCard action={actionWithTechnicalTerms} variant="business" />);

      // Description should be sanitized (playbook -> action, pipeline -> processus automatique)
      // The description text contains the sanitized terms
      expect(screen.getByText(/automatisation/)).toBeInTheDocument(); // Ansible -> automatisation
      expect(screen.getByText(/processus automatique/)).toBeInTheDocument(); // pipeline -> processus automatique
    });

    it('displays original description for default variant', () => {
      renderWithTheme(<ActionCard action={actionWithTechnicalTerms} variant="default" />);

      expect(screen.getByText(/playbook/)).toBeInTheDocument();
    });

    it('is clickable in business variant', () => {
      const handleClick = vi.fn();
      renderWithTheme(
        <ActionCard action={actionWithTechnicalTerms} onClick={handleClick} variant="business" />
      );

      const card = screen.getByRole('article');
      fireEvent.click(card);

      expect(handleClick).toHaveBeenCalledTimes(1);
    });

    it('maintains accessibility in business variant', () => {
      renderWithTheme(<ActionCard action={actionWithTechnicalTerms} variant="business" />);

      const card = screen.getByRole('article');
      expect(card).toHaveAttribute('aria-label');
    });
  });
});

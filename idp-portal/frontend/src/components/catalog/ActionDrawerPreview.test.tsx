import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import { ThemeProvider } from '../../contexts/ThemeContext';
import { ActionDrawerPreview } from './ActionDrawerPreview';
import type { ActionPreviewData } from '../../types/api';

const mockAction: ActionPreviewData = {
  name: 'Creer PDB Oracle',
  description: 'Cree une nouvelle Pluggable Database Oracle sur le serveur cible.',
  engine: 'Oracle',
  platform: 'AAP',
  impact_level: 'high',
  parameters_schema: {
    type: 'object',
    properties: {
      pdb_name: { type: 'string', description: 'Nom du PDB' },
      target_server: { type: 'string', description: 'Serveur cible' },
      size_gb: { type: 'number', description: 'Taille en GB' },
    },
  },
  tags: ['oracle', 'provisioning'],
};

function renderWithTheme(ui: React.ReactElement) {
  return render(<ThemeProvider>{ui}</ThemeProvider>);
}

describe('ActionDrawerPreview', () => {
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
    renderWithTheme(<ActionDrawerPreview action={mockAction} />);

    expect(screen.getByText('Creer PDB Oracle')).toBeInTheDocument();
    expect(screen.getByText(/Cree une nouvelle Pluggable Database/)).toBeInTheDocument();
  });

  it('renders with correct aria-label for accessibility', () => {
    renderWithTheme(<ActionDrawerPreview action={mockAction} />);

    const region = screen.getByRole('region');
    expect(region).toHaveAttribute('aria-label', 'Preview fiche action: Creer PDB Oracle');
  });

  it('renders impact indicator when impact_level is provided', () => {
    renderWithTheme(<ActionDrawerPreview action={mockAction} />);

    expect(screen.getByText('Eleve')).toBeInTheDocument();
  });

  it('renders engine and platform metadata (Story 2.23: category removed)', () => {
    renderWithTheme(<ActionDrawerPreview action={mockAction} />);

    expect(screen.getByText('Oracle')).toBeInTheDocument();
    expect(screen.getByText('AAP')).toBeInTheDocument();
  });

  it('renders parameters from parameters_schema', () => {
    renderWithTheme(<ActionDrawerPreview action={mockAction} />);

    expect(screen.getByText('pdb_name')).toBeInTheDocument();
    expect(screen.getByText('target_server')).toBeInTheDocument();
    expect(screen.getByText('size_gb')).toBeInTheDocument();
  });

  it('renders empty state when no parameters defined', () => {
    const actionWithoutParams = { ...mockAction, parameters_schema: null };
    renderWithTheme(<ActionDrawerPreview action={actionWithoutParams} />);

    expect(screen.getByText('Aucun parametre defini')).toBeInTheDocument();
  });

  it('renders enabled Execute button by default (admin preview mode)', () => {
    renderWithTheme(<ActionDrawerPreview action={mockAction} />);

    const button = screen.getByRole('button', { name: /Executer/i });
    expect(button).toBeInTheDocument();
    expect(button).not.toBeDisabled();
  });

  it('renders disabled Execute button when canExecute is false (Story 3.2, AC3)', () => {
    renderWithTheme(<ActionDrawerPreview action={mockAction} canExecute={false} />);

    const button = screen.getByRole('button', { name: /Executer/i });
    expect(button).toBeInTheDocument();
    expect(button).toBeDisabled();
  });

  it('renders enabled Execute button when canExecute is true (Story 3.2, AC3)', () => {
    renderWithTheme(<ActionDrawerPreview action={mockAction} canExecute={true} allowedEnvironments={['DEV', 'PROD']} />);

    const button = screen.getByRole('button', { name: /Executer/i });
    expect(button).toBeInTheDocument();
    expect(button).not.toBeDisabled();
  });

  it('returns null when visible is false', () => {
    const { container } = renderWithTheme(<ActionDrawerPreview action={mockAction} visible={false} />);

    expect(container.firstChild).toBeNull();
  });

  it('renders placeholder text when name is empty', () => {
    const actionWithoutName = { ...mockAction, name: '' };
    renderWithTheme(<ActionDrawerPreview action={actionWithoutName} />);

    expect(screen.getByText('Sans nom')).toBeInTheDocument();
  });

  it('renders placeholder text when description is null', () => {
    const actionWithoutDesc = { ...mockAction, description: null };
    renderWithTheme(<ActionDrawerPreview action={actionWithoutDesc} />);

    expect(screen.getByText('Aucune description disponible.')).toBeInTheDocument();
  });

  it('has correct aria-label on disabled button (Story 3.2, AC3)', () => {
    renderWithTheme(<ActionDrawerPreview action={mockAction} canExecute={false} />);

    const button = screen.getByRole('button', { name: /Executer/i });
    expect(button).toHaveAttribute('aria-label', 'Executer (acces non autorise)');
  });

  it('renders tags as category (Story 3.2, AC1)', () => {
    renderWithTheme(<ActionDrawerPreview action={mockAction} />);

    expect(screen.getByText('oracle')).toBeInTheDocument();
    expect(screen.getByText('provisioning')).toBeInTheDocument();
  });

  it('renders parameter types from schema (Story 3.2, AC1)', () => {
    renderWithTheme(<ActionDrawerPreview action={mockAction} />);

    // Parameters should show type info (multiple strings expected)
    const stringTypes = screen.getAllByText(': string');
    expect(stringTypes.length).toBeGreaterThanOrEqual(2); // pdb_name and target_server
    expect(screen.getByText(': number')).toBeInTheDocument(); // size_gb
  });

  // === Story 3.4: Documentation section tests (FR12) ===

  it('renders documentation section with Markdown content (Story 3.4, AC1, AC4)', () => {
    const actionWithDocs = {
      ...mockAction,
      documentation_md: '# Getting Started\n\nThis is a **test** action.',
    };
    renderWithTheme(<ActionDrawerPreview action={actionWithDocs} />);

    expect(screen.getByText('Documentation')).toBeInTheDocument();
    expect(screen.getByTestId('documentation-content')).toBeInTheDocument();
    // Rendered Markdown should have the heading and content
    expect(screen.getByText('Getting Started')).toBeInTheDocument();
  });

  it('renders empty state when documentation_md is null (Story 3.4, AC3)', () => {
    const actionWithoutDocs = { ...mockAction, documentation_md: null };
    renderWithTheme(<ActionDrawerPreview action={actionWithoutDocs} />);

    expect(screen.getByText('Documentation')).toBeInTheDocument();
    expect(screen.getByText('Aucune documentation disponible')).toBeInTheDocument();
    expect(screen.getByTestId('documentation-empty')).toBeInTheDocument();
  });

  it('renders empty state when documentation_md is undefined (Story 3.4, AC3)', () => {
    // mockAction has no documentation_md
    renderWithTheme(<ActionDrawerPreview action={mockAction} />);

    expect(screen.getByText('Documentation')).toBeInTheDocument();
    expect(screen.getByText('Aucune documentation disponible')).toBeInTheDocument();
  });

  it('documentation container has scrollable style (Story 3.4, AC2)', () => {
    const actionWithLongDocs = {
      ...mockAction,
      documentation_md: '# Title\n\n' + 'Lorem ipsum dolor sit amet. '.repeat(100),
    };
    renderWithTheme(<ActionDrawerPreview action={actionWithLongDocs} />);

    const container = screen.getByTestId('documentation-content');
    expect(container).toHaveStyle({ overflowY: 'auto' });
    expect(container).toHaveStyle({ maxHeight: '300px' });
  });

  it('renders code blocks in documentation (Story 3.4, AC5)', () => {
    const actionWithCode = {
      ...mockAction,
      documentation_md: '```sql\nSELECT * FROM users;\n```',
    };
    renderWithTheme(<ActionDrawerPreview action={actionWithCode} />);

    expect(screen.getByText('SELECT * FROM users;')).toBeInTheDocument();
  });

  it('renders lists in documentation (Story 3.4, AC5)', () => {
    const actionWithList = {
      ...mockAction,
      documentation_md: '- Item 1\n- Item 2\n- Item 3',
    };
    renderWithTheme(<ActionDrawerPreview action={actionWithList} />);

    expect(screen.getByText('Item 1')).toBeInTheDocument();
    expect(screen.getByText('Item 2')).toBeInTheDocument();
    expect(screen.getByText('Item 3')).toBeInTheDocument();
  });

  it('renders tables in documentation (Story 3.4, AC5)', () => {
    const actionWithTable = {
      ...mockAction,
      documentation_md: '| Col A | Col B |\n|------|------|\n| a1   | b1   |\n| a2   | b2   |',
    };
    renderWithTheme(<ActionDrawerPreview action={actionWithTable} />);

    const docSection = screen.getByTestId('documentation-content');
    expect(within(docSection).getByText('Col A')).toBeInTheDocument();
    expect(within(docSection).getByText('Col B')).toBeInTheDocument();
    expect(within(docSection).getByText('a1')).toBeInTheDocument();
    expect(within(docSection).getByText('b1')).toBeInTheDocument();
    expect(within(docSection).getByText('a2')).toBeInTheDocument();
    expect(within(docSection).getByText('b2')).toBeInTheDocument();
    const table = within(docSection).getByRole('table');
    expect(table).toBeInTheDocument();
  });
});

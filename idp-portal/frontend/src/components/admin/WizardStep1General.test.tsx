import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { Form } from 'antd';
import { WizardStep1General, type WizardStep1GeneralProps } from './WizardStep1General';

vi.mock('../../services/admin_service', () => ({
  checkActionNameAvailable: vi.fn().mockResolvedValue(true),
}));

vi.mock('../common/SectionHelp', () => ({
  default: () => null,
}));

vi.mock('../../contexts/ThemeContext', () => ({
  useTheme: () => ({ mode: 'light', effectiveMode: 'light', setMode: vi.fn(), toggleTheme: vi.fn() }),
}));

const defaultProps: WizardStep1GeneralProps = {
  form: {} as ReturnType<typeof Form.useForm>[0],
  isWorkflow: false,
  showTypeSelector: false,
  isReadOnly: false,
  engineOptions: [{ value: 'Oracle', label: 'Oracle' }],
  enginesLoading: false,
  integrationOptions: [{ value: 1, label: 'AAP-PROD' }],
  integrationsLoading: false,
  isEditMode: false,
  editAction: null,
  selectedTags: [],
  setSelectedTags: vi.fn(),
  tagsOptions: [],
  categoryOptions: [],
  categoriesLoading: false,
  getIntegrationById: vi.fn(() => undefined),
};

function renderWithForm(props: WizardStep1GeneralProps = defaultProps) {
  return render(
    <Form>
      <WizardStep1General {...props} />
    </Form>
  );
}

describe('WizardStep1General', () => {
  it('affiche le champ Nom de l\'action', () => {
    renderWithForm();
    expect(screen.getByPlaceholderText(/Créer PDB Oracle/i)).toBeInTheDocument();
  });

  it('affiche le champ Description', () => {
    renderWithForm();
    expect(screen.getByPlaceholderText('Description...')).toBeInTheDocument();
  });

  it('affiche les champs moteur et intégration pour une action', () => {
    renderWithForm();
    expect(screen.getByText('Moteur de base de données')).toBeInTheDocument();
    expect(screen.getByText('Intégration')).toBeInTheDocument();
  });

  it('masque les champs moteur et intégration pour un workflow', () => {
    renderWithForm({ ...defaultProps, isWorkflow: true });
    expect(screen.queryByText('Moteur de base de données')).not.toBeInTheDocument();
    expect(screen.queryByText('Intégration')).not.toBeInTheDocument();
  });

  it('affiche le sélecteur de type quand showTypeSelector=true', () => {
    renderWithForm({ ...defaultProps, showTypeSelector: true });
    expect(screen.getByRole('radio', { name: /Action/i })).toBeInTheDocument();
    expect(screen.getByRole('radio', { name: /Workflow/i })).toBeInTheDocument();
  });

  it('affiche une alerte mode dégradé pour action legacy sans integration_id', () => {
    const props = {
      ...defaultProps,
      isEditMode: true,
      editAction: {
        id: 1,
        name: 'Test',
        description: 'Test',
        item_type: 'action' as const,
        engine: 'Oracle',
        platform: 'AAP',
        integration_id: null,
        parameters_schema: null,
        impact_rules: null,
        default_impact_level: null,
        status: 'draft' as const,
        created_by: 1,
        created_at: '2026-01-01T00:00:00Z',
        updated_at: null,
        execution_steps: null,
        workflow_steps: null,
        change_type_config: null,
      },
    };
    renderWithForm(props);
    expect(screen.getByText(/ancienne plateforme.*AAP/i)).toBeInTheDocument();
  });
});

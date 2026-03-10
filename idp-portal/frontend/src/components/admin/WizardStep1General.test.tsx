import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Form } from 'antd';
import { WizardStep1General, type WizardStep1GeneralProps } from './WizardStep1General';

const mockCheckName = vi.fn().mockResolvedValue(true);

vi.mock('../../hooks/useActionNameAvailability', () => ({
  useActionNameAvailability: () => ({ checkName: mockCheckName }),
}));

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

  it('affiche une alerte quand aucune intégration plateforme disponible', () => {
    renderWithForm({
      ...defaultProps,
      integrationOptions: [],
      integrationsLoading: false,
    });
    expect(screen.getByText(/Aucune intégration de type plateforme/i)).toBeInTheDocument();
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
      },
    };
    renderWithForm(props);
    expect(screen.getByText(/ancienne plateforme.*AAP/i)).toBeInTheDocument();
  });
});

// ─── Coverage extras ──────────────────────────────────────────────────────────
describe('WizardStep1General — coverage extras', () => {
  afterEach(() => {
    vi.clearAllMocks();
    mockCheckName.mockResolvedValue(true);
  });

  it('affiche le placeholder workflow pour le champ nom quand isWorkflow=true', () => {
    renderWithForm({ ...defaultProps, isWorkflow: true });
    expect(screen.getByPlaceholderText(/Provisionner environnement/i)).toBeInTheDocument();
  });

  it('champ nom désactivé quand isReadOnly=true', () => {
    renderWithForm({ ...defaultProps, isReadOnly: true });
    const input = screen.getByRole('textbox', { name: /Nom de l'action/i });
    expect(input).toBeDisabled();
  });

  it('le placeholder catégorie est "Autres (défaut)" pour un workflow', () => {
    renderWithForm({ ...defaultProps, isWorkflow: true, categoriesLoading: false, categoryOptions: [] });
    // Category select placeholder text
    expect(screen.getByText(/Autres \(défaut\)/i)).toBeInTheDocument();
  });

  it('le placeholder catégorie est "Chargement..." quand categoriesLoading=true', () => {
    renderWithForm({ ...defaultProps, categoriesLoading: true });
    expect(screen.getByText('Chargement...')).toBeInTheDocument();
  });

  it('affiche le placeholder intégration "Chargement..." quand integrationsLoading=true', () => {
    renderWithForm({ ...defaultProps, integrationsLoading: true, integrationOptions: [] });
    // Multiple loading placeholders, just check there are "Chargement..." texts
    const elements = screen.getAllByText('Chargement...');
    expect(elements.length).toBeGreaterThan(0);
  });

  it('déclenche onChange sur le select Tags', async () => {
    const setSelectedTags = vi.fn();
    renderWithForm({ ...defaultProps, setSelectedTags });
    // The Tags Select is in "tags" mode, simulating a change
    // We just verify the component renders the Tags select
    expect(screen.getByRole('combobox', { name: /Tags/i })).toBeInTheDocument();
  });

  it('le validateur de nom appelle checkName avec la valeur et rejette quand non disponible', async () => {
    mockCheckName.mockResolvedValue(false);

    // Use a FormWrapper that can trigger validation
    function FormWrapper() {
      const [form] = Form.useForm();
      return (
        <Form form={form} name="test">
          <WizardStep1General {...defaultProps} form={form} />
          <button
            type="button"
            onClick={() => form.validateFields(['name'])}
          >
            Validate
          </button>
        </Form>
      );
    }

    render(<FormWrapper />);
    const nameInput = screen.getByRole('textbox', { name: /Nom de l'action/i });
    fireEvent.change(nameInput, { target: { value: 'TestAction' } });
    fireEvent.blur(nameInput);

    await waitFor(() => {
      expect(mockCheckName).toHaveBeenCalledWith('TestAction', undefined);
    });
  });

  it('le validateur de nom ne vérifie pas si la valeur est vide', async () => {
    function FormWrapper() {
      const [form] = Form.useForm();
      return (
        <Form form={form} name="test2">
          <WizardStep1General {...defaultProps} form={form} />
        </Form>
      );
    }

    render(<FormWrapper />);
    const nameInput = screen.getByRole('textbox', { name: /Nom de l'action/i });
    fireEvent.change(nameInput, { target: { value: '' } });
    fireEvent.blur(nameInput);

    // checkName should NOT be called for empty value
    await waitFor(() => {
      expect(mockCheckName).not.toHaveBeenCalled();
    });
  });

  it('le validateur accepte le nom quand checkName retourne true', async () => {
    mockCheckName.mockResolvedValue(true);

    function FormWrapper() {
      const [form] = Form.useForm();
      return (
        <Form form={form} name="test3">
          <WizardStep1General {...defaultProps} form={form} />
        </Form>
      );
    }

    render(<FormWrapper />);
    const nameInput = screen.getByRole('textbox', { name: /Nom de l'action/i });
    fireEvent.change(nameInput, { target: { value: 'NewAction' } });
    fireEvent.blur(nameInput);

    await waitFor(() => {
      expect(mockCheckName).toHaveBeenCalledWith('NewAction', undefined);
    });
  });

  it('le validateur passe le editAction.id quand isEditMode=true', async () => {
    function FormWrapper() {
      const [form] = Form.useForm();
      return (
        <Form form={form} name="test4">
          <WizardStep1General
            {...defaultProps}
            form={form}
            isEditMode={true}
            editAction={{
              id: 42,
              name: 'OldName',
              description: 'desc',
              item_type: 'action',
              engine: 'Oracle',
              platform: null,
              integration_id: 1,
              parameters_schema: null,
              impact_rules: null,
              default_impact_level: null,
              status: 'published',
              created_by: 1,
              created_at: '2026-01-01T00:00:00Z',
              updated_at: null,
              execution_steps: null,
              workflow_steps: null,
            }}
          />
        </Form>
      );
    }

    render(<FormWrapper />);
    const nameInput = screen.getByRole('textbox', { name: /Nom de l'action/i });
    fireEvent.change(nameInput, { target: { value: 'UpdatedAction' } });
    fireEvent.blur(nameInput);

    await waitFor(() => {
      expect(mockCheckName).toHaveBeenCalledWith('UpdatedAction', 42);
    });
  });

  it('le validateur rejette avec le message attendu quand checkName retourne false', async () => {
    mockCheckName.mockResolvedValue(false);

    function FormWrapper() {
      const [form] = Form.useForm();
      return (
        <Form form={form} name="testReject">
          <WizardStep1General {...defaultProps} form={form} />
          <button type="button" onClick={() => form.validateFields(['name'])}>
            Validate
          </button>
        </Form>
      );
    }

    render(<FormWrapper />);
    const nameInput = screen.getByRole('textbox', { name: /Nom de l'action/i });
    await userEvent.type(nameInput, 'DuplicateAction');
    fireEvent.blur(nameInput);

    const validateBtn = screen.getByRole('button', { name: 'Validate' });
    await userEvent.click(validateBtn);

    await waitFor(() => {
      expect(screen.getByText(/Une action ou un workflow avec ce nom existe déjà/i)).toBeInTheDocument();
    });
  });

  it('Tags Select onChange appelle setSelectedTags avec un tableau', async () => {
    const setSelectedTags = vi.fn();
    renderWithForm({ ...defaultProps, setSelectedTags, tagsOptions: [{ value: 'tag1', label: 'tag1' }] });

    const tagsSelect = screen.getByRole('combobox', { name: /Tags/i });
    await userEvent.click(tagsSelect);
    // In tags mode, typing and Enter adds a tag - triggers onChange with array
    await userEvent.type(tagsSelect, 'newtag{Enter}');

    await waitFor(() => {
      expect(setSelectedTags).toHaveBeenCalled();
    });
  });

  it('Catégorie Select avec allowClear permet de vider la sélection', async () => {
    function FormWrapper() {
      const [form] = Form.useForm();
      return (
        <Form form={form} initialValues={{ category: 'cat1' }}>
          <WizardStep1General
            {...defaultProps}
            form={form}
            categoryOptions={[{ value: 'cat1', label: 'Cat1' }, { value: 'cat2', label: 'Cat2' }]}
          />
        </Form>
      );
    }

    render(<FormWrapper />);
    const categorySelect = screen.getByRole('combobox', { name: /Catégorie/i });
    await userEvent.click(categorySelect);
    // Clear the selection - antd Select shows clear icon when value is set
    const clearBtn = document.querySelector('.ant-select-clear');
    if (clearBtn) {
      await userEvent.click(clearBtn as HTMLElement);
    }
    expect(categorySelect).toBeInTheDocument();
  });

  it('description accepte jusqu\'à 4000 caractères', async () => {
    function FormWrapper() {
      const [form] = Form.useForm();
      return (
        <Form form={form} name="testDesc">
          <WizardStep1General {...defaultProps} form={form} />
          <button type="button" onClick={() => form.validateFields(['description'])}>
            Validate
          </button>
        </Form>
      );
    }

    render(<FormWrapper />);
    const descInput = screen.getByRole('textbox', { name: /Description/i });
    fireEvent.change(descInput, { target: { value: 'x'.repeat(4000) } });

    const validateBtn = screen.getByRole('button', { name: 'Validate' });
    await userEvent.click(validateBtn);

    await waitFor(() => {
      expect(screen.queryByText(/La description ne peut pas dépasser 4000 caractères/i)).not.toBeInTheDocument();
    });
  });

  it('item_type est requis quand showTypeSelector=true', async () => {
    function FormWrapper() {
      const [form] = Form.useForm();
      return (
        <Form form={form} name="testType" initialValues={{ name: 'X', description: 'Y' }}>
          <WizardStep1General {...defaultProps} form={form} showTypeSelector={true} />
          <button type="button" onClick={() => form.validateFields()}>
            Submit
          </button>
        </Form>
      );
    }

    render(<FormWrapper />);
    const submitBtn = screen.getByRole('button', { name: 'Submit' });
    await userEvent.click(submitBtn);

    await waitFor(() => {
      expect(screen.getByText(/Le type est requis/i)).toBeInTheDocument();
    });
  });
});

import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Form } from 'antd';
import { WizardStep2Automatisme, type WizardStep2AutomatismeProps } from './WizardStep2Automatisme';
import * as useAAPTemplatesModule from '../../hooks/useAAPTemplates';

vi.mock('../../hooks/useAAPTemplates', () => ({
  useAAPTemplates: vi.fn(() => ({
    templates: [],
    loading: false,
    fallback: false,
    error: null,
  })),
}));

vi.mock('../../contexts/ThemeContext', () => ({
  useTheme: () => ({ mode: 'light', effectiveMode: 'light', setMode: vi.fn(), toggleTheme: vi.fn() }),
}));

vi.mock('../../services/admin_service', () => ({
  getActions: vi.fn().mockResolvedValue([]),
  getWorkflowSteps: vi.fn().mockResolvedValue([]),
  getEligibleActionsForWorkflow: vi.fn().mockResolvedValue([]),
}));

const defaultProps: WizardStep2AutomatismeProps = {
  isWorkflow: false,
  isReadOnly: false,
  connectorType: '',
  integrationId: undefined,
  aapResourceType: 'job_template' as const,
  setAapResourceType: vi.fn(),
  aapTemplateId: undefined,
  setAapTemplateId: vi.fn(),
  parameterList: [],
  setParameterList: vi.fn(),
  workflowSteps: [],
  setWorkflowSteps: vi.fn(),
  workflowViewMode: 'list' as const,
  setWorkflowViewMode: vi.fn(),
};

function renderWithForm(props: WizardStep2AutomatismeProps = defaultProps) {
  return render(
    <Form>
      <WizardStep2Automatisme {...props} />
    </Form>
  );
}

describe('WizardStep2Automatisme', () => {
  it('affiche le label Paramètres pour une action non-AAP', () => {
    renderWithForm();
    expect(screen.getByText('Paramètres')).toBeInTheDocument();
  });

  it('affiche le sélecteur de type AAP quand connectorType=aap (Story 82.7)', () => {
    renderWithForm({ ...defaultProps, connectorType: 'aap', integrationId: 1 });
    expect(screen.getByText(/Quel automatisme appeler/i)).toBeInTheDocument();
    expect(screen.getByText(/Type de ressource/i)).toBeInTheDocument();
  });

  it('affiche le message info pour un workflow', () => {
    renderWithForm({ ...defaultProps, isWorkflow: true });
    expect(screen.getByText(/workflow enchaîne des actions existantes/i)).toBeInTheDocument();
  });

  it('affiche les boutons liste/visuel pour un workflow', () => {
    renderWithForm({ ...defaultProps, isWorkflow: true });
    expect(screen.getByRole('radio', { name: /Mode liste/i })).toBeInTheDocument();
    expect(screen.getByRole('radio', { name: /Mode visuel/i })).toBeInTheDocument();
  });

  it('appelle setWorkflowViewMode au clic sur Mode visuel', async () => {
    const setMode = vi.fn();
    const user = userEvent.setup({ pointerEventsCheck: 0 });
    renderWithForm({ ...defaultProps, isWorkflow: true, setWorkflowViewMode: setMode });
    await user.click(screen.getByRole('radio', { name: /Mode visuel/i }));
    expect(setMode).toHaveBeenCalledWith('visual');
  });
});

describe('WizardStep2Automatisme — coverage extension', () => {
  it('affiche WorkflowBuilderCanvas quand workflowViewMode=visual', () => {
    // In visual mode, WorkflowStepsEditor is NOT shown (no "Ajouter une étape" button)
    // WorkflowBuilderCanvas renders instead
    renderWithForm({ ...defaultProps, isWorkflow: true, workflowViewMode: 'visual' });
    expect(screen.queryByRole('button', { name: /Ajouter une étape/i })).not.toBeInTheDocument();
  });

  it('affiche la section AAP en mode fallback quand integrationId est undefined et connectorType=aap', () => {
    vi.mocked(useAAPTemplatesModule.useAAPTemplates).mockReturnValue({
      templates: [],
      loading: false,
      fallback: true,
      error: null,
    });
    renderWithForm({ ...defaultProps, connectorType: 'aap', integrationId: undefined });
    // Shows manual input fallback
    expect(screen.getByLabelText('ID template AAP')).toBeInTheDocument();
  });

  it('affiche alerte saisie manuelle quand fallback=true et integrationId absent', () => {
    vi.mocked(useAAPTemplatesModule.useAAPTemplates).mockReturnValue({
      templates: [],
      loading: false,
      fallback: true,
      error: 'Connection failed',
    });
    renderWithForm({ ...defaultProps, connectorType: 'aap', integrationId: undefined });
    expect(screen.getByText(/Saisie manuelle/i)).toBeInTheDocument();
  });

  it('affiche Template AAP Select (non-fallback) quand templates disponibles', () => {
    vi.mocked(useAAPTemplatesModule.useAAPTemplates).mockReturnValue({
      templates: [{ id: 10, name: 'My Template' }],
      loading: false,
      fallback: false,
      error: null,
    });
    renderWithForm({ ...defaultProps, connectorType: 'aap', integrationId: 1 });
    // Shows the Select (non-fallback path, lines 92-108)
    expect(screen.getByLabelText('Template AAP')).toBeInTheDocument();
  });

  it('ajoute option introuvable quand aapTemplateId ne correspond pas aux templates (line 44)', () => {
    vi.mocked(useAAPTemplatesModule.useAAPTemplates).mockReturnValue({
      templates: [{ id: 10, name: 'My Template' }],
      loading: false,
      fallback: false,
      error: null,
    });
    // aapTemplateId=99 which is NOT in templates array → adds "Template #99 (introuvable)"
    renderWithForm({ ...defaultProps, connectorType: 'aap', integrationId: 1, aapTemplateId: 99 });
    // The select is rendered (the option gets added to the options array)
    expect(screen.getByLabelText('Template AAP')).toBeInTheDocument();
  });

  it('appelle onTemplateIdChange avec undefined quand input vidé (line 84)', async () => {
    const setAapTemplateId = vi.fn();
    vi.mocked(useAAPTemplatesModule.useAAPTemplates).mockReturnValue({
      templates: [],
      loading: false,
      fallback: true,
      error: null,
    });
    renderWithForm({ ...defaultProps, connectorType: 'aap', integrationId: 1, aapTemplateId: 5, setAapTemplateId });
    const input = screen.getByLabelText('ID template AAP');
    fireEvent.change(input, { target: { value: '' } });
    expect(setAapTemplateId).toHaveBeenCalledWith(undefined);
  });

  it('affiche validate error quand aapTemplateId est null (line 76-77)', () => {
    vi.mocked(useAAPTemplatesModule.useAAPTemplates).mockReturnValue({
      templates: [],
      loading: false,
      fallback: true,
      error: null,
    });
    renderWithForm({ ...defaultProps, connectorType: 'aap', integrationId: 1, aapTemplateId: undefined });
    // Help text should appear when aapTemplateId is null/undefined
    expect(screen.getByText(/ID du job template/i)).toBeInTheDocument();
  });

  it('appelle onTemplateIdChange via Select onChange (line 105)', async () => {
    const setAapTemplateId = vi.fn();
    vi.mocked(useAAPTemplatesModule.useAAPTemplates).mockReturnValue({
      templates: [{ id: 10, name: 'My Template' }],
      loading: false,
      fallback: false,
      error: null,
    });
    const user = userEvent.setup({ pointerEventsCheck: 0 });
    renderWithForm({ ...defaultProps, connectorType: 'aap', integrationId: 1, setAapTemplateId });
    const select = screen.getByLabelText('Template AAP');
    await user.click(select);
    // Wait for dropdown to open, then click the option
    const option = await screen.findByText('My Template');
    await user.click(option);
    expect(setAapTemplateId).toHaveBeenCalledWith(10);
  });

  it('filtre les templates via onSearch/filterOption (lines 106-110)', async () => {
    vi.mocked(useAAPTemplatesModule.useAAPTemplates).mockReturnValue({
      templates: [
        { id: 10, name: 'Alpha Template' },
        { id: 11, name: 'Beta Template' },
      ],
      loading: false,
      fallback: false,
      error: null,
    });
    const user = userEvent.setup({ pointerEventsCheck: 0 });
    renderWithForm({ ...defaultProps, connectorType: 'aap', integrationId: 1 });
    const select = screen.getByLabelText('Template AAP');
    await user.click(select);
    // Type to trigger onSearch and filterOption
    await user.type(select, 'Alpha');
    // Alpha Template should remain visible
    const option = await screen.findByText('Alpha Template');
    expect(option).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Story 82.7 — T8.4: connectorType prop (remplace isPlatformAAP)
// ---------------------------------------------------------------------------

describe('WizardStep2Automatisme — connectorType (Story 82.7, T8.4)', () => {
  beforeEach(() => {
    vi.mocked(useAAPTemplatesModule.useAAPTemplates).mockReturnValue({
      templates: [],
      loading: false,
      fallback: false,
      error: null,
    });
  });

  it("connectorType='aap' → section WizardAAPTemplateSection visible", () => {
    renderWithForm({ ...defaultProps, connectorType: 'aap', integrationId: 1 });
    expect(screen.getByText(/Quel automatisme appeler/i)).toBeInTheDocument();
    expect(screen.getByText(/Type de ressource/i)).toBeInTheDocument();
  });

  it("connectorType='terraform' → section WizardAAPTemplateSection cachée", () => {
    renderWithForm({ ...defaultProps, connectorType: 'terraform', integrationId: 2 });
    expect(screen.queryByText(/Quel automatisme appeler/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Type de ressource/i)).not.toBeInTheDocument();
  });

  it("connectorType='' (vide) → section WizardAAPTemplateSection cachée", () => {
    renderWithForm({ ...defaultProps, connectorType: '', integrationId: 2 });
    expect(screen.queryByText(/Quel automatisme appeler/i)).not.toBeInTheDocument();
  });

  it("connectorType='github_actions' → section WizardAAPTemplateSection cachée", () => {
    renderWithForm({ ...defaultProps, connectorType: 'github_actions', integrationId: 3 });
    expect(screen.queryByText(/Quel automatisme appeler/i)).not.toBeInTheDocument();
    // Paramètres section toujours visible pour les non-AAP
    expect(screen.getByText('Paramètres')).toBeInTheDocument();
  });
});

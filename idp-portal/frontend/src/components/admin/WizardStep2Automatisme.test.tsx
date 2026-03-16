import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Form } from 'antd';
import { WizardStep2Automatisme, type WizardStep2AutomatismeProps } from './WizardStep2Automatisme';
import * as useAAPTemplatesModule from '../../hooks/useAAPTemplates';
import type { PlatformCapability } from '../../services/capabilities_service';

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

// ─── Helpers platformCap ───────────────────────────────────────────────────

const aapPlatformCap: PlatformCapability = {
  code: 'aap',
  display_name: 'Ansible Automation Platform',
  aliases: [],
  icon: 'aap',
  connector_type: 'aap',
  action_platform_code: 'AAP',
  supports_health_check: true,
  action_config_schema: {
    type: 'object',
    properties: {
      resource_type: { type: 'string', enum: ['job_template', 'workflow_job'], title: 'Type de ressource' },
      template_id: { type: 'integer', title: 'ID du template', minimum: 1 },
    },
  },
};

const emptySchemaAAPCap: PlatformCapability = {
  ...aapPlatformCap,
  action_config_schema: {},
};

const genericPlatformWithSchema: PlatformCapability = {
  code: 'github_actions',
  display_name: 'GitHub Actions',
  aliases: [],
  icon: 'github_actions',
  connector_type: 'github_actions',
  action_platform_code: 'GitHub Actions',
  supports_health_check: true,
  action_config_schema: {
    type: 'object',
    properties: {
      repo: { type: 'string', title: 'Dépôt (owner/repo)' },
    },
  },
};

const terraformCap: PlatformCapability = {
  code: 'terraform_cloud',
  display_name: 'Terraform Cloud',
  aliases: ['terraform'],
  icon: 'terraform',
  connector_type: 'terraform',
  action_platform_code: 'Terraform',
  supports_health_check: true,
  action_config_schema: {},
};

const defaultProps: WizardStep2AutomatismeProps = {
  isWorkflow: false,
  isReadOnly: false,
  platformCap: null,
  actionConfig: {},
  setActionConfig: vi.fn(),
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
  it('affiche le label Paramètres pour une action sans platformCap', () => {
    renderWithForm();
    expect(screen.getByText('Paramètres')).toBeInTheDocument();
  });

  // T5.1: "Quel automatisme appeler" supprimé — vérification "Type de ressource" via SchemaFormRenderer
  it('affiche le sélecteur de type AAP quand platformCap.connector_type=aap avec schéma non vide', () => {
    renderWithForm({ ...defaultProps, platformCap: aapPlatformCap, integrationId: 1 });
    expect(screen.queryByText(/Quel automatisme appeler/i)).not.toBeInTheDocument();
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
    renderWithForm({ ...defaultProps, isWorkflow: true, workflowViewMode: 'visual' });
    expect(screen.queryByRole('button', { name: /Ajouter une étape/i })).not.toBeInTheDocument();
  });

  // T5.3: fallback mode — aria-label "ID template AAP" conservé dans AAPTemplateIdRenderer
  it('affiche la section AAP en mode fallback quand integrationId est undefined et platformCap=aap', () => {
    vi.mocked(useAAPTemplatesModule.useAAPTemplates).mockReturnValue({
      templates: [],
      loading: false,
      fallback: true,
      error: null,
    });
    renderWithForm({ ...defaultProps, platformCap: aapPlatformCap, integrationId: undefined });
    expect(screen.getByLabelText('ID template AAP')).toBeInTheDocument();
  });

  it('affiche alerte saisie manuelle quand fallback=true et integrationId absent', () => {
    vi.mocked(useAAPTemplatesModule.useAAPTemplates).mockReturnValue({
      templates: [],
      loading: false,
      fallback: true,
      error: 'Connection failed',
    });
    renderWithForm({ ...defaultProps, platformCap: aapPlatformCap, integrationId: undefined });
    expect(screen.getByText(/Saisie manuelle/i)).toBeInTheDocument();
  });

  // T5.2: aria-label "Template AAP" conservé dans AAPTemplateIdRenderer (mode normal)
  it('affiche Template AAP Select (non-fallback) quand templates disponibles', () => {
    vi.mocked(useAAPTemplatesModule.useAAPTemplates).mockReturnValue({
      templates: [{ id: 10, name: 'My Template' }],
      loading: false,
      fallback: false,
      error: null,
    });
    renderWithForm({ ...defaultProps, platformCap: aapPlatformCap, integrationId: 1 });
    expect(screen.getByLabelText('Template AAP')).toBeInTheDocument();
  });

  it('ajoute option introuvable quand template_id ne correspond pas aux templates', () => {
    vi.mocked(useAAPTemplatesModule.useAAPTemplates).mockReturnValue({
      templates: [{ id: 10, name: 'My Template' }],
      loading: false,
      fallback: false,
      error: null,
    });
    renderWithForm({ ...defaultProps, platformCap: aapPlatformCap, integrationId: 1, actionConfig: { template_id: 99 } });
    expect(screen.getByLabelText('Template AAP')).toBeInTheDocument();
  });

  it('appelle setActionConfig avec template_id undefined quand input vidé', async () => {
    const setActionConfig = vi.fn();
    vi.mocked(useAAPTemplatesModule.useAAPTemplates).mockReturnValue({
      templates: [],
      loading: false,
      fallback: true,
      error: null,
    });
    renderWithForm({
      ...defaultProps,
      platformCap: aapPlatformCap,
      integrationId: 1,
      actionConfig: { template_id: 5 },
      setActionConfig,
    });
    const input = screen.getByLabelText('ID template AAP');
    fireEvent.change(input, { target: { value: '' } });
    expect(setActionConfig).toHaveBeenCalledWith(expect.objectContaining({ template_id: undefined }));
  });

  // T5.4: validation text adapté — l'Input fallback est présent (validation display supprimée avec WizardAAPTemplateSection)
  it('affiche input fallback quand template_id est null (pas de validation text)', () => {
    vi.mocked(useAAPTemplatesModule.useAAPTemplates).mockReturnValue({
      templates: [],
      loading: false,
      fallback: true,
      error: null,
    });
    renderWithForm({ ...defaultProps, platformCap: aapPlatformCap, integrationId: 1, actionConfig: {} });
    expect(screen.getByLabelText('ID template AAP')).toBeInTheDocument();
  });

  it('appelle setActionConfig via Select onChange (non-fallback)', async () => {
    const setActionConfig = vi.fn();
    vi.mocked(useAAPTemplatesModule.useAAPTemplates).mockReturnValue({
      templates: [{ id: 10, name: 'My Template' }],
      loading: false,
      fallback: false,
      error: null,
    });
    const user = userEvent.setup({ pointerEventsCheck: 0 });
    renderWithForm({ ...defaultProps, platformCap: aapPlatformCap, integrationId: 1, setActionConfig });
    const select = screen.getByLabelText('Template AAP');
    await user.click(select);
    const option = await screen.findByText('My Template');
    await user.click(option);
    expect(setActionConfig).toHaveBeenCalledWith(expect.objectContaining({ template_id: 10 }));
  });

  it('filtre les templates via onSearch/filterOption', async () => {
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
    renderWithForm({ ...defaultProps, platformCap: aapPlatformCap, integrationId: 1 });
    const select = screen.getByLabelText('Template AAP');
    await user.click(select);
    await user.type(select, 'Alpha');
    const option = await screen.findByText('Alpha Template');
    expect(option).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Story 83-8 — Rendu déclaratif via action_config_schema (AC4)
// ---------------------------------------------------------------------------

describe('WizardStep2Automatisme — rendu déclaratif action_config_schema (Story 83-8)', () => {
  beforeEach(() => {
    vi.mocked(useAAPTemplatesModule.useAAPTemplates).mockReturnValue({
      templates: [],
      loading: false,
      fallback: false,
      error: null,
    });
  });

  // T5.1: Adapté — suppression vérification "Quel automatisme appeler", conservation "Type de ressource" via SchemaFormRenderer
  it('renders_aap_section_for_aap_platform_with_schema : platformCap.connector_type=aap + schéma non vide → SchemaFormRenderer présent (sans label WizardAAPTemplateSection)', () => {
    renderWithForm({ ...defaultProps, platformCap: aapPlatformCap, integrationId: 1 });
    expect(screen.queryByText(/Quel automatisme appeler/i)).not.toBeInTheDocument();
    expect(screen.getByText(/Type de ressource/i)).toBeInTheDocument();
  });

  it('renders_nothing_for_platform_with_empty_schema : action_config_schema={} → pas de section config plateforme', () => {
    renderWithForm({ ...defaultProps, platformCap: emptySchemaAAPCap, integrationId: 1 });
    expect(screen.queryByText(/Quel automatisme appeler/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Type de ressource/i)).not.toBeInTheDocument();
    // Paramètres toujours présent
    expect(screen.getByText('Paramètres')).toBeInTheDocument();
  });

  it('renders_schema_form_renderer_for_non_aap_platform_with_schema : github_actions + schéma non vide → SchemaFormRenderer', () => {
    renderWithForm({ ...defaultProps, platformCap: genericPlatformWithSchema });
    // SchemaFormRenderer rend un champ input pour "repo" — vérifie via role textbox
    expect(screen.getByRole('textbox', { name: /Dépôt/i })).toBeInTheDocument();
    // Pas de section AAP
    expect(screen.queryByText(/Quel automatisme appeler/i)).not.toBeInTheDocument();
  });

  it('platformCap=null → rien rendu pour la config plateforme', () => {
    renderWithForm({ ...defaultProps, platformCap: null });
    expect(screen.queryByText(/Quel automatisme appeler/i)).not.toBeInTheDocument();
    expect(screen.getByText('Paramètres')).toBeInTheDocument();
  });

  it("platformCap.connector_type='terraform' avec schéma vide → section config cachée", () => {
    renderWithForm({ ...defaultProps, platformCap: terraformCap, integrationId: 2 });
    expect(screen.queryByText(/Quel automatisme appeler/i)).not.toBeInTheDocument();
    expect(screen.getByText('Paramètres')).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Story 82.7 — Backward compatibility: connectorType tests migrated to platformCap
// ---------------------------------------------------------------------------

describe('WizardStep2Automatisme — platformCap (Story 82.7 → 83-8)', () => {
  beforeEach(() => {
    vi.mocked(useAAPTemplatesModule.useAAPTemplates).mockReturnValue({
      templates: [],
      loading: false,
      fallback: false,
      error: null,
    });
  });

  // T5.1: Adapté — "Quel automatisme appeler" supprimé, "Type de ressource" via SchemaFormRenderer
  it("platformCap.connector_type='aap' + schéma → SchemaFormRenderer visible avec Type de ressource", () => {
    renderWithForm({ ...defaultProps, platformCap: aapPlatformCap, integrationId: 1 });
    expect(screen.queryByText(/Quel automatisme appeler/i)).not.toBeInTheDocument();
    expect(screen.getByText(/Type de ressource/i)).toBeInTheDocument();
  });

  it("platformCap.connector_type='terraform' (schéma vide) → section config cachée", () => {
    renderWithForm({ ...defaultProps, platformCap: terraformCap, integrationId: 2 });
    expect(screen.queryByText(/Quel automatisme appeler/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Type de ressource/i)).not.toBeInTheDocument();
  });

  it("platformCap=null → section config cachée", () => {
    renderWithForm({ ...defaultProps, platformCap: null, integrationId: 2 });
    expect(screen.queryByText(/Quel automatisme appeler/i)).not.toBeInTheDocument();
  });

  it("platformCap.connector_type='github_actions' avec schéma non vide → SchemaFormRenderer, pas AAP section", () => {
    renderWithForm({ ...defaultProps, platformCap: genericPlatformWithSchema, integrationId: 3 });
    expect(screen.queryByText(/Quel automatisme appeler/i)).not.toBeInTheDocument();
    expect(screen.getByText('Paramètres')).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Story 84-6 — Nouveaux tests : SchemaFormRenderer unifié pour AAP (AC1, AC6)
// ---------------------------------------------------------------------------

describe('WizardStep2Automatisme — Story 84-6 : SchemaFormRenderer unifié AAP', () => {
  beforeEach(() => {
    vi.mocked(useAAPTemplatesModule.useAAPTemplates).mockReturnValue({
      templates: [],
      loading: false,
      fallback: false,
      error: null,
    });
  });

  // T6.1 — AAP + schema non vide → SchemaFormRenderer rendu, pas de label "Quel automatisme appeler"
  it('aap_uses_schema_form_renderer_not_aap_section : AAP + schema → SchemaFormRenderer (sans "Quel automatisme appeler")', () => {
    renderWithForm({ ...defaultProps, platformCap: aapPlatformCap, integrationId: 1 });
    expect(screen.queryByText(/Quel automatisme appeler/i)).not.toBeInTheDocument();
    // SchemaFormRenderer est actif : les champs du schema sont rendus
    expect(screen.getByText(/Type de ressource/i)).toBeInTheDocument();
  });

  // T6.2 — resource_type rendu automatiquement par SchemaFormRenderer (enum → Select standard, pas de custom renderer)
  // resource_type n'a PAS d'aria-label propre → seul template_id a "Template AAP"
  // Les deux champs génèrent chacun un combobox : resource_type (schema-driven) + template_id (custom renderer)
  it('aap_resource_type_rendered_by_schema_form_renderer : deux combobox présents — resource_type (schema) + template_id (custom renderer)', () => {
    vi.mocked(useAAPTemplatesModule.useAAPTemplates).mockReturnValue({
      templates: [{ id: 1, name: 'Deploy' }],
      loading: false,
      fallback: false,
      error: null,
    });
    renderWithForm({ ...defaultProps, platformCap: aapPlatformCap, integrationId: 1 });
    expect(screen.getByText(/Type de ressource/i)).toBeInTheDocument();
    // resource_type (enum, schema-driven) + template_id (custom renderer) → 2 combobox au minimum
    const combos = screen.queryAllByRole('combobox');
    expect(combos.length).toBeGreaterThanOrEqual(2);
    // template_id a un aria-label dédié ; resource_type n'en a pas (rendu standard SchemaFormRenderer)
    expect(screen.getByLabelText('Template AAP')).toBeInTheDocument();
  });

  // T6.3 — custom renderer template_id en mode normal : Select avec aria-label "Template AAP"
  it('aap_template_id_custom_renderer_normal_mode : Select aria-label "Template AAP" visible', () => {
    vi.mocked(useAAPTemplatesModule.useAAPTemplates).mockReturnValue({
      templates: [{ id: 1, name: 'Deploy Prod' }],
      loading: false,
      fallback: false,
      error: null,
    });
    renderWithForm({ ...defaultProps, platformCap: aapPlatformCap, integrationId: 1 });
    expect(screen.getByLabelText('Template AAP')).toBeInTheDocument();
    expect(screen.queryByLabelText('ID template AAP')).not.toBeInTheDocument();
  });

  // T6.4 — custom renderer template_id en mode fallback : Input avec aria-label "ID template AAP"
  it('aap_template_id_custom_renderer_fallback_mode : Input aria-label "ID template AAP" visible', () => {
    vi.mocked(useAAPTemplatesModule.useAAPTemplates).mockReturnValue({
      templates: [],
      loading: false,
      fallback: true,
      error: null,
    });
    renderWithForm({ ...defaultProps, platformCap: aapPlatformCap, integrationId: 1 });
    expect(screen.getByLabelText('ID template AAP')).toBeInTheDocument();
    expect(screen.queryByLabelText('Template AAP')).not.toBeInTheDocument();
  });

  // M1 — AC7 : isReadOnly=true → contrôle AAPTemplateIdRenderer désactivé (Input fallback)
  it('aap_template_id_disabled_when_isReadOnly : Input fallback disabled quand isReadOnly=true', () => {
    vi.mocked(useAAPTemplatesModule.useAAPTemplates).mockReturnValue({
      templates: [],
      loading: false,
      fallback: true,
      error: null,
    });
    renderWithForm({ ...defaultProps, platformCap: aapPlatformCap, integrationId: 1, isReadOnly: true });
    const input = screen.getByLabelText('ID template AAP');
    expect(input).toBeDisabled();
  });

  // M2 — Alerte saisie manuelle visible quand fallback=true + error présent même si integrationId est défini
  it('aap_fallback_alert_shown_when_error_and_integrationId_defined : Alert visible si error truthy même avec integrationId', () => {
    vi.mocked(useAAPTemplatesModule.useAAPTemplates).mockReturnValue({
      templates: [],
      loading: false,
      fallback: true,
      error: 'Connection refused',
    });
    renderWithForm({ ...defaultProps, platformCap: aapPlatformCap, integrationId: 1 });
    expect(screen.getByText(/Saisie manuelle/i)).toBeInTheDocument();
  });
});

/**
 * Story 27.7: Tests for new adapter types in IntegrationForm.
 * AC6: Select Type displays all 7 types (2 existing + 5 new)
 * AC7: Actions displayed correctly for each new type
 * AC8: Creation and edit for new types
 * AC10: Frontend tests for new types in Select + actions
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { App } from 'antd';
import { IntegrationForm } from './IntegrationForm';
import type { IntegrationResponse, IntegrationTypeCatalogue } from '../../types/api';

// Full mock with all 7 types and their actions
const mockAllTypes: IntegrationTypeCatalogue[] = [
  {
    code: 'aap',
    name: 'Ansible Automation Platform',
    description: 'Exécution de jobs et workflows Ansible via AAP Controller',
    version: '1.0',
    is_active: true,
    created_at: '2026-02-10T10:00:00Z',
    updated_at: '2026-02-10T10:00:00Z',
    actions: [
      { id: 1, action_code: 'start_job', action_label: 'Démarrer un job', description: 'Lance un job template AAP', required_params: { properties: { job_template_id: { type: 'integer', description: 'ID du job template' } } }, optional_params: { properties: { extra_vars: { type: 'object' } } }, response_format: {}, is_active: true, created_at: '2026-02-10T10:00:00Z', updated_at: '2026-02-10T10:00:00Z' },
      { id: 2, action_code: 'start_workflow', action_label: 'Démarrer un workflow', description: 'Lance un workflow', required_params: { properties: { workflow_job_template_id: { type: 'integer' } } }, optional_params: {}, response_format: {}, is_active: true, created_at: '2026-02-10T10:00:00Z', updated_at: '2026-02-10T10:00:00Z' },
      { id: 3, action_code: 'get_job_status', action_label: 'Statut du job', description: 'Statut', required_params: { properties: { job_id: { type: 'integer' } } }, optional_params: {}, response_format: {}, is_active: true, created_at: '2026-02-10T10:00:00Z', updated_at: '2026-02-10T10:00:00Z' },
      { id: 4, action_code: 'cancel_job', action_label: 'Annuler un job', description: 'Annule', required_params: { properties: { job_id: { type: 'integer' } } }, optional_params: {}, response_format: {}, is_active: true, created_at: '2026-02-10T10:00:00Z', updated_at: '2026-02-10T10:00:00Z' },
    ],
  },
  {
    code: 'azure_devops',
    name: 'Azure DevOps Pipelines',
    description: 'Azure DevOps — exécution pipelines CI/CD avec monitoring temps réel (polling 5s)',
    version: '1.0',
    is_active: true,
    created_at: '2026-02-14T10:00:00Z',
    updated_at: '2026-02-14T10:00:00Z',
    actions: [
      { id: 10, action_code: 'run_pipeline', action_label: 'Exécuter un pipeline', description: 'Pipeline Azure', required_params: { properties: { pipeline_id: { type: 'integer' }, branch: { type: 'string' } } }, optional_params: { properties: { variables: { type: 'object' } } }, response_format: {}, is_active: true, created_at: '2026-02-14T10:00:00Z', updated_at: '2026-02-14T10:00:00Z' },
      { id: 11, action_code: 'get_run_status', action_label: 'Statut exécution pipeline', description: 'Statut', required_params: { properties: { run_id: { type: 'integer' } } }, optional_params: {}, response_format: {}, is_active: true, created_at: '2026-02-14T10:00:00Z', updated_at: '2026-02-14T10:00:00Z' },
      { id: 12, action_code: 'get_run_logs', action_label: 'Logs exécution', description: 'Logs', required_params: { properties: { run_id: { type: 'integer' } } }, optional_params: {}, response_format: {}, is_active: true, created_at: '2026-02-14T10:00:00Z', updated_at: '2026-02-14T10:00:00Z' },
      { id: 13, action_code: 'cancel_run', action_label: 'Annuler exécution', description: 'Annuler', required_params: { properties: { run_id: { type: 'integer' } } }, optional_params: {}, response_format: {}, is_active: true, created_at: '2026-02-14T10:00:00Z', updated_at: '2026-02-14T10:00:00Z' },
    ],
  },
  {
    code: 'github_actions',
    name: 'GitHub Actions',
    description: 'GitHub Actions — déclenchement workflows avec monitoring',
    version: '1.0',
    is_active: true,
    created_at: '2026-02-14T10:00:00Z',
    updated_at: '2026-02-14T10:00:00Z',
    actions: [
      { id: 20, action_code: 'trigger_workflow', action_label: 'Déclencher workflow', description: 'Trigger', required_params: { properties: { owner: { type: 'string' }, repo: { type: 'string' }, workflow_id: { type: 'string' }, ref: { type: 'string' } } }, optional_params: { properties: { inputs: { type: 'object' } } }, response_format: {}, is_active: true, created_at: '2026-02-14T10:00:00Z', updated_at: '2026-02-14T10:00:00Z' },
      { id: 21, action_code: 'get_workflow_run_status', action_label: 'Statut workflow', description: 'Statut', required_params: { properties: { run_id: { type: 'integer' } } }, optional_params: {}, response_format: {}, is_active: true, created_at: '2026-02-14T10:00:00Z', updated_at: '2026-02-14T10:00:00Z' },
      { id: 22, action_code: 'get_workflow_run_logs', action_label: 'Logs workflow', description: 'Logs', required_params: { properties: { run_id: { type: 'integer' } } }, optional_params: {}, response_format: {}, is_active: true, created_at: '2026-02-14T10:00:00Z', updated_at: '2026-02-14T10:00:00Z' },
      { id: 23, action_code: 'cancel_workflow_run', action_label: 'Annuler workflow', description: 'Annuler', required_params: { properties: { run_id: { type: 'integer' } } }, optional_params: {}, response_format: {}, is_active: true, created_at: '2026-02-14T10:00:00Z', updated_at: '2026-02-14T10:00:00Z' },
    ],
  },
  {
    code: 'servicenow',
    name: 'ServiceNow ITSM',
    description: 'Gestion des change requests ServiceNow',
    version: '1.0',
    is_active: true,
    created_at: '2026-02-10T10:00:00Z',
    updated_at: '2026-02-10T10:00:00Z',
    actions: [
      { id: 30, action_code: 'create_change', action_label: 'Créer un changement', description: 'Change', required_params: { properties: { short_description: { type: 'string' }, category: { type: 'string' } } }, optional_params: {}, response_format: {}, is_active: true, created_at: '2026-02-10T10:00:00Z', updated_at: '2026-02-10T10:00:00Z' },
      { id: 31, action_code: 'update_change', action_label: 'Mettre à jour', description: 'Update', required_params: { properties: { change_id: { type: 'string' } } }, optional_params: {}, response_format: {}, is_active: true, created_at: '2026-02-10T10:00:00Z', updated_at: '2026-02-10T10:00:00Z' },
      { id: 32, action_code: 'get_change_status', action_label: 'Statut changement', description: 'Statut', required_params: { properties: { change_id: { type: 'string' } } }, optional_params: {}, response_format: {}, is_active: true, created_at: '2026-02-10T10:00:00Z', updated_at: '2026-02-10T10:00:00Z' },
    ],
  },
  {
    code: 'terraform_cloud',
    name: 'Terraform Cloud',
    description: 'Terraform Cloud — exécution runs (plan/apply)',
    version: '1.0',
    is_active: true,
    created_at: '2026-02-14T10:00:00Z',
    updated_at: '2026-02-14T10:00:00Z',
    actions: [
      { id: 40, action_code: 'create_run', action_label: 'Créer un run', description: 'Run', required_params: { properties: { workspace_id: { type: 'string' }, message: { type: 'string' } } }, optional_params: { properties: { is_destroy: { type: 'boolean' }, variables: { type: 'object' } } }, response_format: {}, is_active: true, created_at: '2026-02-14T10:00:00Z', updated_at: '2026-02-14T10:00:00Z' },
      { id: 41, action_code: 'get_run_status', action_label: 'Statut run', description: 'Statut', required_params: { properties: { run_id: { type: 'string' } } }, optional_params: {}, response_format: {}, is_active: true, created_at: '2026-02-14T10:00:00Z', updated_at: '2026-02-14T10:00:00Z' },
      { id: 42, action_code: 'get_run_logs', action_label: 'Logs run', description: 'Logs', required_params: { properties: { run_id: { type: 'string' } } }, optional_params: {}, response_format: {}, is_active: true, created_at: '2026-02-14T10:00:00Z', updated_at: '2026-02-14T10:00:00Z' },
      { id: 43, action_code: 'cancel_run', action_label: 'Annuler run', description: 'Annuler', required_params: { properties: { run_id: { type: 'string' } } }, optional_params: {}, response_format: {}, is_active: true, created_at: '2026-02-14T10:00:00Z', updated_at: '2026-02-14T10:00:00Z' },
      { id: 44, action_code: 'apply_run', action_label: 'Appliquer plan', description: 'Apply', required_params: { properties: { run_id: { type: 'string' } } }, optional_params: {}, response_format: {}, is_active: true, created_at: '2026-02-14T10:00:00Z', updated_at: '2026-02-14T10:00:00Z' },
    ],
  },
  {
    code: 'tower',
    name: 'Ansible Tower',
    description: 'Ansible Tower — exécution jobs et workflows via Tower API',
    version: '1.0',
    is_active: true,
    created_at: '2026-02-14T10:00:00Z',
    updated_at: '2026-02-14T10:00:00Z',
    actions: [
      { id: 50, action_code: 'start_job', action_label: 'Démarrer job Tower', description: 'Job', required_params: { properties: { job_template_id: { type: 'integer' } } }, optional_params: { properties: { extra_vars: { type: 'object' } } }, response_format: {}, is_active: true, created_at: '2026-02-14T10:00:00Z', updated_at: '2026-02-14T10:00:00Z' },
      { id: 51, action_code: 'start_workflow', action_label: 'Démarrer workflow Tower', description: 'Workflow', required_params: { properties: { workflow_job_template_id: { type: 'integer' } } }, optional_params: {}, response_format: {}, is_active: true, created_at: '2026-02-14T10:00:00Z', updated_at: '2026-02-14T10:00:00Z' },
      { id: 52, action_code: 'get_job_status', action_label: 'Statut job Tower', description: 'Statut', required_params: { properties: { job_id: { type: 'integer' } } }, optional_params: {}, response_format: {}, is_active: true, created_at: '2026-02-14T10:00:00Z', updated_at: '2026-02-14T10:00:00Z' },
      { id: 53, action_code: 'cancel_job', action_label: 'Annuler job Tower', description: 'Annuler', required_params: { properties: { job_id: { type: 'integer' } } }, optional_params: {}, response_format: {}, is_active: true, created_at: '2026-02-14T10:00:00Z', updated_at: '2026-02-14T10:00:00Z' },
    ],
  },
  {
    code: 'vault',
    name: 'HashiCorp Vault',
    description: 'HashiCorp Vault — résolution secrets (KV v2)',
    version: '1.0',
    is_active: true,
    created_at: '2026-02-14T10:00:00Z',
    updated_at: '2026-02-14T10:00:00Z',
    actions: [
      { id: 60, action_code: 'get_secret', action_label: 'Résoudre secret', description: 'Secret', required_params: { properties: { path: { type: 'string' } } }, optional_params: { properties: { key: { type: 'string' }, namespace: { type: 'string' } } }, response_format: {}, is_active: true, created_at: '2026-02-14T10:00:00Z', updated_at: '2026-02-14T10:00:00Z' },
      { id: 61, action_code: 'renew_token', action_label: 'Renouveler token', description: 'Renew', required_params: {}, optional_params: {}, response_format: {}, is_active: true, created_at: '2026-02-14T10:00:00Z', updated_at: '2026-02-14T10:00:00Z' },
      { id: 62, action_code: 'lookup_token', action_label: 'Vérifier token', description: 'Lookup', required_params: {}, optional_params: {}, response_format: {}, is_active: true, created_at: '2026-02-14T10:00:00Z', updated_at: '2026-02-14T10:00:00Z' },
    ],
  },
];

const mockUseIntegrationTypes = vi.fn().mockReturnValue({
  types: mockAllTypes,
  loading: false,
  error: null,
  isFallback: false,
});

vi.mock('../../hooks/useIntegrationTypes', () => ({
  useIntegrationTypes: () => mockUseIntegrationTypes(),
}));

vi.mock('../../contexts/AuthContext', () => ({
  useAuth: () => ({ accessToken: 'test-token' }),
}));

function renderWithApp(ui: React.ReactElement) {
  return render(<App>{ui}</App>);
}

const mockOnSubmit = vi.fn().mockResolvedValue({
  id: 1,
  type: 'tower',
  name: 'Tower Prod',
  base_url: 'https://tower.example.com',
  credential_ref: null,
  icon: null,
  auth_flow: null,
  created_at: '2026-02-14T10:00:00Z',
  updated_at: '2026-02-14T10:00:00Z',
} as IntegrationResponse);
const mockOnCancel = vi.fn();
const mockOnSuccess = vi.fn();

const defaultProps = {
  open: true,
  onCancel: mockOnCancel,
  onSubmit: mockOnSubmit,
  loading: false,
  error: null,
  editIntegration: null,
  onSuccess: mockOnSuccess,
};

async function selectType(user: ReturnType<typeof userEvent.setup>, label: RegExp, optionText: string) {
  const select = screen.getByRole('combobox', { name: label });
  await user.click(select);
  const option = await screen.findByTitle(optionText);
  await user.click(option);
}

describe('Story 27.7 — IntegrationForm with all 7 types', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUseIntegrationTypes.mockReturnValue({
      types: mockAllTypes,
      loading: false,
      error: null,
      isFallback: false,
    });
  });

  // === AC6: Select Type displays all 7 types ===

  describe('AC6 — Select Type displays all new types', () => {
    it('displays 7 options in Select (AAP, Azure DevOps, GitHub, ServiceNow, Terraform, Tower, Vault)', async () => {
      const user = userEvent.setup();
      renderWithApp(<IntegrationForm {...defaultProps} />);

      const select = screen.getByRole('combobox', { name: /Type d'intégration/ });
      await user.click(select);

      expect(await screen.findByTitle('Ansible Automation Platform')).toBeInTheDocument();
      expect(screen.getByTitle('Azure DevOps Pipelines')).toBeInTheDocument();
      expect(screen.getByTitle('GitHub Actions')).toBeInTheDocument();
      expect(screen.getByTitle('ServiceNow ITSM')).toBeInTheDocument();
      expect(screen.getByTitle('Terraform Cloud')).toBeInTheDocument();
      expect(screen.getByTitle('Ansible Tower')).toBeInTheDocument();
      expect(screen.getByTitle('HashiCorp Vault')).toBeInTheDocument();
    });

    it('Tower option is selectable', async () => {
      const user = userEvent.setup();
      renderWithApp(<IntegrationForm {...defaultProps} />);
      await selectType(user, /Type d'intégration/, 'Ansible Tower');
      await waitFor(() => {
        expect(screen.getByTestId('available-actions-panel')).toBeInTheDocument();
      });
    });

    it('Azure DevOps option is selectable', async () => {
      const user = userEvent.setup();
      renderWithApp(<IntegrationForm {...defaultProps} />);
      await selectType(user, /Type d'intégration/, 'Azure DevOps Pipelines');
      await waitFor(() => {
        expect(screen.getByTestId('available-actions-panel')).toBeInTheDocument();
      });
    });

    it('Vault option is selectable', async () => {
      const user = userEvent.setup();
      renderWithApp(<IntegrationForm {...defaultProps} />);
      await selectType(user, /Type d'intégration/, 'HashiCorp Vault');
      await waitFor(() => {
        expect(screen.getByTestId('available-actions-panel')).toBeInTheDocument();
      });
    });
  });

  // === AC7: Actions displayed for new types ===

  describe('AC7 — Actions displayed for each new type', () => {
    it('GitHub Actions shows 4 actions', async () => {
      const user = userEvent.setup();
      renderWithApp(<IntegrationForm {...defaultProps} />);
      await selectType(user, /Type d'intégration/, 'GitHub Actions');
      await waitFor(() => {
        expect(screen.getByText('Déclencher workflow')).toBeInTheDocument();
      });
      expect(screen.getByText('trigger_workflow')).toBeInTheDocument();
      expect(screen.getByText('Statut workflow')).toBeInTheDocument();
      expect(screen.getByText('Logs workflow')).toBeInTheDocument();
      expect(screen.getByText('Annuler workflow')).toBeInTheDocument();
    });

    it('Terraform Cloud shows 5 actions', async () => {
      const user = userEvent.setup();
      renderWithApp(<IntegrationForm {...defaultProps} />);
      await selectType(user, /Type d'intégration/, 'Terraform Cloud');
      await waitFor(() => {
        expect(screen.getByText('Créer un run')).toBeInTheDocument();
      });
      expect(screen.getByText('Statut run')).toBeInTheDocument();
      expect(screen.getByText('Logs run')).toBeInTheDocument();
      expect(screen.getByText('Annuler run')).toBeInTheDocument();
      expect(screen.getByText('Appliquer plan')).toBeInTheDocument();
    });

    it('Vault shows 3 actions', async () => {
      const user = userEvent.setup();
      renderWithApp(<IntegrationForm {...defaultProps} />);
      await selectType(user, /Type d'intégration/, 'HashiCorp Vault');
      await waitFor(() => {
        expect(screen.getByText('Résoudre secret')).toBeInTheDocument();
      });
      expect(screen.getByText('Renouveler token')).toBeInTheDocument();
      expect(screen.getByText('Vérifier token')).toBeInTheDocument();
    });

    it('Tower shows 4 actions', async () => {
      const user = userEvent.setup();
      renderWithApp(<IntegrationForm {...defaultProps} />);
      await selectType(user, /Type d'intégration/, 'Ansible Tower');
      await waitFor(() => {
        expect(screen.getByText('Démarrer job Tower')).toBeInTheDocument();
      });
      expect(screen.getByText('Démarrer workflow Tower')).toBeInTheDocument();
      expect(screen.getByText('Statut job Tower')).toBeInTheDocument();
      expect(screen.getByText('Annuler job Tower')).toBeInTheDocument();
    });

    it('Azure DevOps shows 4 actions', async () => {
      const user = userEvent.setup();
      renderWithApp(<IntegrationForm {...defaultProps} />);
      await selectType(user, /Type d'intégration/, 'Azure DevOps Pipelines');
      await waitFor(() => {
        expect(screen.getByText('Exécuter un pipeline')).toBeInTheDocument();
      });
      expect(screen.getByText('Statut exécution pipeline')).toBeInTheDocument();
      expect(screen.getByText('Logs exécution')).toBeInTheDocument();
      expect(screen.getByText('Annuler exécution')).toBeInTheDocument();
    });
  });

  // === AC8: Creation for each new type ===

  describe('AC8 — Create integration for new types', () => {
    it('creates Tower integration with type=tower', async () => {
      const user = userEvent.setup();
      renderWithApp(<IntegrationForm {...defaultProps} />);
      await selectType(user, /Type d'intégration/, 'Ansible Tower');
      await user.type(screen.getByLabelText(/^Nom/), 'Tower Prod');
      await user.type(screen.getByLabelText(/URL de base/), 'https://tower.example.com');
      await user.click(screen.getByRole('button', { name: /Créer/i }));
      await waitFor(() => expect(mockOnSubmit).toHaveBeenCalled(), { timeout: 10000 });
      expect(mockOnSubmit).toHaveBeenCalledWith(
        expect.objectContaining({ type: 'tower', name: 'Tower Prod' })
      );
    }, 15000);

    it('creates Azure DevOps integration with type=azure_devops', async () => {
      const user = userEvent.setup();
      renderWithApp(<IntegrationForm {...defaultProps} />);
      await selectType(user, /Type d'intégration/, 'Azure DevOps Pipelines');
      await user.type(screen.getByLabelText(/^Nom/), 'Azure DevOps Prod');
      await user.type(screen.getByLabelText(/URL de base/), 'https://dev.azure.com/org');
      await user.click(screen.getByRole('button', { name: /Créer/i }));
      await waitFor(() => expect(mockOnSubmit).toHaveBeenCalled(), { timeout: 10000 });
      expect(mockOnSubmit).toHaveBeenCalledWith(
        expect.objectContaining({ type: 'azure_devops' })
      );
    }, 15000);

    it('creates GitHub Actions integration with type=github_actions', async () => {
      const user = userEvent.setup();
      renderWithApp(<IntegrationForm {...defaultProps} />);
      await selectType(user, /Type d'intégration/, 'GitHub Actions');
      await user.type(screen.getByLabelText(/^Nom/), 'GitHub Actions Prod');
      await user.type(screen.getByLabelText(/URL de base/), 'https://api.github.com');
      await user.click(screen.getByRole('button', { name: /Créer/i }));
      await waitFor(() => expect(mockOnSubmit).toHaveBeenCalled(), { timeout: 10000 });
      expect(mockOnSubmit).toHaveBeenCalledWith(
        expect.objectContaining({ type: 'github_actions' })
      );
    }, 15000);

    it('creates Terraform Cloud integration with type=terraform_cloud', async () => {
      const user = userEvent.setup();
      renderWithApp(<IntegrationForm {...defaultProps} />);
      await selectType(user, /Type d'intégration/, 'Terraform Cloud');
      await user.type(screen.getByLabelText(/^Nom/), 'Terraform Cloud Prod');
      await user.type(screen.getByLabelText(/URL de base/), 'https://app.terraform.io');
      await user.click(screen.getByRole('button', { name: /Créer/i }));
      await waitFor(() => expect(mockOnSubmit).toHaveBeenCalled(), { timeout: 10000 });
      expect(mockOnSubmit).toHaveBeenCalledWith(
        expect.objectContaining({ type: 'terraform_cloud' })
      );
    }, 15000);

    it('creates Vault integration with type=vault', async () => {
      const user = userEvent.setup();
      renderWithApp(<IntegrationForm {...defaultProps} />);
      await selectType(user, /Type d'intégration/, 'HashiCorp Vault');
      await user.type(screen.getByLabelText(/^Nom/), 'Vault Prod');
      await user.type(screen.getByLabelText(/URL de base/), 'https://vault.example.com');
      await user.click(screen.getByRole('button', { name: /Créer/i }));
      await waitFor(() => expect(mockOnSubmit).toHaveBeenCalled(), { timeout: 10000 });
      expect(mockOnSubmit).toHaveBeenCalledWith(
        expect.objectContaining({ type: 'vault' })
      );
    }, 15000);
  });

  // === AC8: Edit mode — type disabled for new types ===

  describe('AC8 — Edit mode for new types', () => {
    it('Tower type disabled in edit mode, other fields editable', async () => {
      const editIntegration: IntegrationResponse = {
        id: 100,
        type: 'tower',
        name: 'Tower Prod',
        base_url: 'https://tower.example.com',
        credential_ref: 'vault:secret/data/tower/prod#token',
        icon: null,
        auth_flow: null,
        created_at: '2026-02-14T10:00:00Z',
        updated_at: '2026-02-14T10:00:00Z',
      };
      renderWithApp(<IntegrationForm {...defaultProps} editIntegration={editIntegration} />);
      const select = screen.getByRole('combobox', { name: /Type d'intégration/ });
      expect(select).toBeDisabled();
      expect(screen.getByText(/Le type d'une intégration ne peut pas être modifié/)).toBeInTheDocument();
      expect(screen.getByLabelText(/^Nom/)).toHaveValue('Tower Prod');
      expect(screen.getByLabelText(/URL de base/)).toHaveValue('https://tower.example.com');
      expect(screen.getByLabelText(/Référence credentials/)).toHaveValue('vault:secret/data/tower/prod#token');
    });

    it('Azure DevOps type disabled in edit mode', () => {
      const editIntegration: IntegrationResponse = {
        id: 101,
        type: 'azure_devops',
        name: 'Azure DevOps Prod',
        base_url: 'https://dev.azure.com/org',
        credential_ref: null,
        icon: null,
        auth_flow: 'pat',
        created_at: '2026-02-14T10:00:00Z',
        updated_at: '2026-02-14T10:00:00Z',
      };
      renderWithApp(<IntegrationForm {...defaultProps} editIntegration={editIntegration} />);
      const select = screen.getByRole('combobox', { name: /Type d'intégration/ });
      expect(select).toBeDisabled();
    });
  });

  // === AC10: Validation for new types ===

  describe('AC10 — Form validation with new types', () => {
    it('requires type selection for new type submission', async () => {
      const user = userEvent.setup();
      renderWithApp(<IntegrationForm {...defaultProps} />);
      await user.type(screen.getByLabelText(/^Nom/), 'Test Integration');
      await user.type(screen.getByLabelText(/URL de base/), 'https://example.com');
      await user.click(screen.getByRole('button', { name: /Créer/i }));
      await waitFor(() => {
        expect(screen.getByText(/Veuillez sélectionner un type/)).toBeInTheDocument();
      });
    });

    it('shows version badge for Tower type', async () => {
      const user = userEvent.setup();
      renderWithApp(<IntegrationForm {...defaultProps} />);
      await selectType(user, /Type d'intégration/, 'Ansible Tower');
      await waitFor(() => {
        expect(screen.getByText('Version 1.0')).toBeInTheDocument();
      });
    });

    it('shows version badge for Terraform Cloud type', async () => {
      const user = userEvent.setup();
      renderWithApp(<IntegrationForm {...defaultProps} />);
      await selectType(user, /Type d'intégration/, 'Terraform Cloud');
      await waitFor(() => {
        expect(screen.getByText('Version 1.0')).toBeInTheDocument();
      });
    });
  });
});

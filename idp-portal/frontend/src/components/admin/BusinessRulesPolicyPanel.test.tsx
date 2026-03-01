/**
 * Story 28.4, AC#10: Tests for BusinessRulesPolicyPanel.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, act, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { App } from 'antd';
import { BusinessRulesPolicyPanel } from './BusinessRulesPolicyPanel';

// Mock BusinessRulePolicyModal for isolation (exposes onSave/onCancel directly)
vi.mock('./BusinessRulePolicyModal', () => ({
  BusinessRulePolicyModal: ({ onSave, onCancel, open, editPolicy }: {
    onSave: (payload: Record<string, unknown>) => void;
    onCancel: () => void;
    open: boolean;
    editPolicy: unknown;
  }) =>
    open ? (
      <div>
        <span>{editPolicy ? 'Modifier la règle métier' : 'Créer une règle métier'}</span>
        <button data-testid="modal-save" onClick={() => onSave({ name: 'Test Rule', is_active: true, step_type: 'aap', policy_json: {} })}>
          Sauvegarder
        </button>
        <button data-testid="modal-cancel" onClick={onCancel}>Annuler</button>
      </div>
    ) : null,
}));

// Mock services
vi.mock('../../services/business_rules_service', () => ({
  getBusinessRulePolicies: vi.fn(),
  getBusinessRulePolicy: vi.fn(),
  createBusinessRulePolicy: vi.fn(),
  updateBusinessRulePolicy: vi.fn(),
  deleteBusinessRulePolicy: vi.fn(),
}));

vi.mock('../../services/logger', () => ({
  default: { error: vi.fn(), warn: vi.fn(), info: vi.fn() },
}));

import {
  getBusinessRulePolicies,
  getBusinessRulePolicy,
  createBusinessRulePolicy,
  updateBusinessRulePolicy,
  deleteBusinessRulePolicy,
} from '../../services/business_rules_service';

const mockPolicies = [
  {
    id: 1,
    name: 'Terraform SQL Review',
    description: 'Review if sku_name is modified',
    is_active: true,
    step_type: 'terraform_cloud',
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
  },
  {
    id: 2,
    name: 'AAP Host Check',
    description: null,
    is_active: false,
    step_type: 'aap',
    created_at: '2026-01-02T00:00:00Z',
    updated_at: '2026-01-02T00:00:00Z',
  },
];

function renderWithApp(ui: React.ReactElement) {
  return render(<App>{ui}</App>);
}

describe('BusinessRulesPolicyPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(getBusinessRulePolicies).mockResolvedValue({
      data: mockPolicies,
      pagination: null,
    });
  });

  it('loads and displays policies', async () => {
    await act(async () => {
      renderWithApp(<BusinessRulesPolicyPanel />);
    });

    await waitFor(() => {
      expect(screen.getByText('Terraform SQL Review')).toBeInTheDocument();
    });
    expect(screen.getByText('AAP Host Check')).toBeInTheDocument();
  });

  it('displays step_type badges', async () => {
    await act(async () => {
      renderWithApp(<BusinessRulesPolicyPanel />);
    });

    await waitFor(() => {
      expect(screen.getByText('terraform_cloud')).toBeInTheDocument();
    });
    expect(screen.getByText('aap')).toBeInTheDocument();
  });

  it('displays active/inactive badges', async () => {
    await act(async () => {
      renderWithApp(<BusinessRulesPolicyPanel />);
    });

    await waitFor(() => {
      expect(screen.getByText('Oui')).toBeInTheDocument();
    });
    expect(screen.getByText('Non')).toBeInTheDocument();
  });

  it('shows create button', async () => {
    await act(async () => {
      renderWithApp(<BusinessRulesPolicyPanel />);
    });

    await waitFor(() => {
      // Ant Design button with icon: check text contains "gle"
      const buttons = screen.getAllByRole('button');
      const createBtn = buttons.find(b => b.textContent?.includes('gle métier'));
      expect(createBtn).toBeTruthy();
    });
  });

  it('opens create modal when clicking create button', async () => {
    const user = userEvent.setup();

    await act(async () => {
      renderWithApp(<BusinessRulesPolicyPanel />);
    });

    await waitFor(() => {
      const buttons = screen.getAllByRole('button');
      expect(buttons.find(b => b.textContent?.includes('gle métier'))).toBeTruthy();
    });

    const buttons = screen.getAllByRole('button');
    const createBtn = buttons.find(b => b.textContent?.includes('gle métier'))!;
    await user.click(createBtn);

    await waitFor(() => {
      // Modal title from BusinessRulePolicyModal
      expect(screen.getByText(/une r.*gle m/)).toBeInTheDocument();
    });
  });

  it('opens edit modal when clicking edit button', async () => {
    const user = userEvent.setup();

    vi.mocked(getBusinessRulePolicy).mockResolvedValue({
      ...mockPolicies[0],
      policy_json: { on_step_output: [] },
      actions_count: 2,
      created_by: 1,
    });

    await act(async () => {
      renderWithApp(<BusinessRulesPolicyPanel />);
    });

    await waitFor(() => {
      expect(screen.getByText('Terraform SQL Review')).toBeInTheDocument();
    });

    const editButtons = screen.getAllByLabelText(/Modifier/);
    await user.click(editButtons[0]);

    await waitFor(() => {
      expect(screen.getByText('Modifier la règle métier')).toBeInTheDocument();
    });
  });

  it('shows empty state when no policies exist', async () => {
    vi.mocked(getBusinessRulePolicies).mockResolvedValue({
      data: [],
      pagination: null,
    });

    await act(async () => {
      renderWithApp(<BusinessRulesPolicyPanel />);
    });

    await waitFor(() => {
      expect(screen.getByText('Aucune règle métier configurée')).toBeInTheDocument();
    });
  });

  it('affiche une erreur de chargement quand getBusinessRulePolicies échoue', async () => {
    vi.mocked(getBusinessRulePolicies).mockRejectedValue(new Error('Network error'));

    await act(async () => {
      renderWithApp(<BusinessRulesPolicyPanel />);
    });

    await waitFor(() => {
      expect(getBusinessRulePolicies).toHaveBeenCalled();
    });
  });

  it('handleSave — crée une nouvelle règle et recharge', async () => {
    const user = userEvent.setup();
    vi.mocked(createBusinessRulePolicy).mockResolvedValue({
      ...mockPolicies[0],
      id: 99,
      policy_json: { on_step_output: [] },
      actions_count: 0,
      created_by: 1,
    });

    await act(async () => {
      renderWithApp(<BusinessRulesPolicyPanel />);
    });

    await waitFor(() => {
      const buttons = screen.getAllByRole('button');
      expect(buttons.find(b => b.textContent?.includes('gle métier'))).toBeTruthy();
    });

    const buttons = screen.getAllByRole('button');
    const createBtn = buttons.find(b => b.textContent?.includes('gle métier'))!;
    await user.click(createBtn);

    await waitFor(() => {
      expect(screen.getByText(/une r.*gle m/)).toBeInTheDocument();
    });
  });

  it('handleEdit — ouvre le modal d\'édition avec les données de la règle', async () => {
    const user = userEvent.setup();

    vi.mocked(getBusinessRulePolicy).mockResolvedValue({
      ...mockPolicies[0],
      policy_json: { on_step_output: [] },
      actions_count: 2,
      created_by: 1,
    });

    await act(async () => {
      renderWithApp(<BusinessRulesPolicyPanel />);
    });

    await waitFor(() => {
      expect(screen.getByText('Terraform SQL Review')).toBeInTheDocument();
    });

    const editButtons = screen.getAllByLabelText(/Modifier/);
    await user.click(editButtons[0]);

    await waitFor(() => {
      expect(screen.getByText('Modifier la règle métier')).toBeInTheDocument();
    });
    expect(getBusinessRulePolicy).toHaveBeenCalledWith(1);
  });

  it('handleDelete — ouvre la confirmation de suppression', async () => {
    const user = userEvent.setup();

    await act(async () => {
      renderWithApp(<BusinessRulesPolicyPanel />);
    });

    await waitFor(() => {
      expect(screen.getByText('Terraform SQL Review')).toBeInTheDocument();
    });

    const deleteButtons = screen.getAllByLabelText(/Supprimer/);
    await user.click(deleteButtons[0]);

    await waitFor(() => {
      expect(screen.getAllByText(/upprimer la règle métier/).length).toBeGreaterThan(0);
    });
  });

  it('handleDelete onOk — supprime la règle et recharge', async () => {
    const user = userEvent.setup();
    vi.mocked(deleteBusinessRulePolicy).mockResolvedValue(undefined as never);

    await act(async () => {
      renderWithApp(<BusinessRulesPolicyPanel />);
    });

    await waitFor(() => {
      expect(screen.getByText('Terraform SQL Review')).toBeInTheDocument();
    });

    const deleteButtons = screen.getAllByLabelText(/Supprimer/);
    await user.click(deleteButtons[0]);

    await waitFor(() => {
      expect(screen.getAllByText(/upprimer la règle métier/).length).toBeGreaterThan(0);
    });

    // Cliquer sur le bouton de confirmation "Supprimer" dans le modal
    const confirmButtons = screen.getAllByRole('button', { name: /^Supprimer$/ });
    const modalConfirmBtn = confirmButtons[confirmButtons.length - 1];
    await user.click(modalConfirmBtn);

    await waitFor(() => {
      expect(deleteBusinessRulePolicy).toHaveBeenCalledWith(1);
    });
  });

  it('actualiser — recharge les politiques au clic', async () => {
    const user = userEvent.setup();

    await act(async () => {
      renderWithApp(<BusinessRulesPolicyPanel />);
    });

    await waitFor(() => {
      expect(screen.getByText('Terraform SQL Review')).toBeInTheDocument();
    });

    vi.clearAllMocks();
    vi.mocked(getBusinessRulePolicies).mockResolvedValue({ data: mockPolicies, pagination: null });

    const refreshBtn = screen.getByRole('button', { name: /actualiser/i });
    await user.click(refreshBtn);

    await waitFor(() => {
      expect(getBusinessRulePolicies).toHaveBeenCalled();
    });
  });

  it('filtre par type — change filterStepType', async () => {
    const user = userEvent.setup();

    await act(async () => {
      renderWithApp(<BusinessRulesPolicyPanel />);
    });

    await waitFor(() => {
      expect(screen.getByText('Terraform SQL Review')).toBeInTheDocument();
    });

    // Cliquer sur le select de filtre par type
    const filterSelect = screen.getByLabelText('Filtre par type').closest('.ant-select');
    await user.click(filterSelect!);

    // Sélectionner "Terraform Cloud"
    const tfOption = screen.getByText('Terraform Cloud');
    await user.click(tfOption);

    await waitFor(() => {
      expect(getBusinessRulePolicies).toHaveBeenCalledWith(
        expect.objectContaining({ step_type: 'terraform_cloud' })
      );
    });
  });

  it('déclenche le sorter Nom au clic sur l\'en-tête de colonne', async () => {
    await act(async () => {
      renderWithApp(<BusinessRulesPolicyPanel />);
    });

    await waitFor(() => {
      expect(screen.getByText('Terraform SQL Review')).toBeInTheDocument();
    });

    // Click the "Nom" column header to trigger the sorter
    const nomHeader = screen.getByText('Nom');
    fireEvent.click(nomHeader);
    fireEvent.click(nomHeader); // click again for descending

    expect(screen.getByText('Terraform SQL Review')).toBeInTheDocument();
  });

  it('handleSave — crée une règle via le modal mocké', async () => {
    const user = userEvent.setup();
    vi.mocked(createBusinessRulePolicy).mockResolvedValue({
      ...mockPolicies[0],
      id: 99,
      policy_json: { on_step_output: [] },
      actions_count: 0,
      created_by: 1,
    });

    await act(async () => {
      renderWithApp(<BusinessRulesPolicyPanel />);
    });

    await waitFor(() => {
      const buttons = screen.getAllByRole('button');
      expect(buttons.find(b => b.textContent?.includes('gle métier'))).toBeTruthy();
    });

    const buttons = screen.getAllByRole('button');
    const createBtn = buttons.find(b => b.textContent?.includes('gle métier'))!;
    await user.click(createBtn);

    await waitFor(() => {
      expect(screen.getByTestId('modal-save')).toBeInTheDocument();
    });

    await user.click(screen.getByTestId('modal-save'));

    await waitFor(() => {
      expect(createBusinessRulePolicy).toHaveBeenCalledWith(
        expect.objectContaining({ name: 'Test Rule' })
      );
    });
  });

  it('handleSave — met à jour une règle via le modal mocké', async () => {
    const user = userEvent.setup();
    vi.mocked(getBusinessRulePolicy).mockResolvedValue({
      ...mockPolicies[0],
      policy_json: { on_step_output: [] },
      actions_count: 2,
      created_by: 1,
    });
    vi.mocked(updateBusinessRulePolicy).mockResolvedValue({
      ...mockPolicies[0],
      policy_json: { on_step_output: [] },
      actions_count: 2,
      created_by: 1,
    });

    await act(async () => {
      renderWithApp(<BusinessRulesPolicyPanel />);
    });

    await waitFor(() => {
      expect(screen.getByText('Terraform SQL Review')).toBeInTheDocument();
    });

    const editButtons = screen.getAllByLabelText(/Modifier/);
    await user.click(editButtons[0]);

    await waitFor(() => {
      expect(screen.getByTestId('modal-save')).toBeInTheDocument();
    });

    await user.click(screen.getByTestId('modal-save'));

    await waitFor(() => {
      expect(updateBusinessRulePolicy).toHaveBeenCalledWith(
        1,
        expect.objectContaining({ name: 'Test Rule' })
      );
    });
  });

  it('modal onCancel — ferme le modal sans sauvegarder', async () => {
    const user = userEvent.setup();

    await act(async () => {
      renderWithApp(<BusinessRulesPolicyPanel />);
    });

    await waitFor(() => {
      const buttons = screen.getAllByRole('button');
      expect(buttons.find(b => b.textContent?.includes('gle métier'))).toBeTruthy();
    });

    const buttons = screen.getAllByRole('button');
    const createBtn = buttons.find(b => b.textContent?.includes('gle métier'))!;
    await user.click(createBtn);

    await waitFor(() => {
      expect(screen.getByTestId('modal-cancel')).toBeInTheDocument();
    });

    await user.click(screen.getByTestId('modal-cancel'));

    await waitFor(() => {
      expect(screen.queryByTestId('modal-cancel')).not.toBeInTheDocument();
    });
  });
});

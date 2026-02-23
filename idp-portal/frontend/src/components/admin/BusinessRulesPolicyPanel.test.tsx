/**
 * Story 28.4, AC#10: Tests for BusinessRulesPolicyPanel.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { App } from 'antd';
import { BusinessRulesPolicyPanel } from './BusinessRulesPolicyPanel';

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
      const createBtn = buttons.find(b => b.textContent?.includes('gle m'));
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
      expect(buttons.find(b => b.textContent?.includes('gle m'))).toBeTruthy();
    });

    const buttons = screen.getAllByRole('button');
    const createBtn = buttons.find(b => b.textContent?.includes('gle m'))!;
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
});

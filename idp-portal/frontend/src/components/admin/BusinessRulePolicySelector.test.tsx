/**
 * Story 28.4, AC#10: Tests for BusinessRulePolicySelector.
 * Inline option removed — only "Aucune" and "Règle prédéfinie", filtered by stepType.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { App } from 'antd';
import { BusinessRulePolicySelector } from './BusinessRulePolicySelector';

vi.mock('../../services/business_rules_service', () => ({
  getBusinessRulePolicies: vi.fn(),
  getBusinessRulePolicy: vi.fn(),
}));

import { getBusinessRulePolicies } from '../../services/business_rules_service';

const mockPolicies = [
  {
    id: 1,
    name: 'Terraform SQL Review',
    description: 'Review if sku_name modified',
    is_active: true,
    step_type: 'terraform_cloud',
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
  },
  {
    id: 2,
    name: 'AAP Host Check',
    description: 'Check host status',
    is_active: true,
    step_type: 'aap',
    created_at: '2026-01-02T00:00:00Z',
    updated_at: '2026-01-02T00:00:00Z',
  },
];

function renderWithApp(ui: React.ReactElement) {
  return render(<App>{ui}</App>);
}

describe('BusinessRulePolicySelector', () => {
  const defaultProps = {
    policyId: null as number | null,
    onPolicyIdChange: vi.fn(),
    stepType: 'terraform_cloud',
  };

  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(getBusinessRulePolicies).mockResolvedValue({
      data: mockPolicies,
      pagination: null,
    });
  });

  it('renders two radio options (Aucune, Règle prédéfinie)', async () => {
    await act(async () => {
      renderWithApp(<BusinessRulePolicySelector {...defaultProps} />);
    });

    const radios = screen.getAllByRole('radio');
    expect(radios).toHaveLength(2);
  });

  it('defaults to "none" mode when no policy selected', async () => {
    await act(async () => {
      renderWithApp(<BusinessRulePolicySelector {...defaultProps} />);
    });

    const radios = screen.getAllByRole('radio');
    expect(radios[0]).toBeChecked();
  });

  it('selects "predefined" mode when policyId is set', async () => {
    await act(async () => {
      renderWithApp(
        <BusinessRulePolicySelector {...defaultProps} policyId={1} />,
      );
    });

    const radios = screen.getAllByRole('radio');
    expect(radios[1]).toBeChecked();
  });

  it('fetches policies with step_type when stepType is provided', async () => {
    await act(async () => {
      renderWithApp(<BusinessRulePolicySelector {...defaultProps} />);
    });

    expect(getBusinessRulePolicies).toHaveBeenCalledWith({
      is_active: true,
      step_type: 'terraform_cloud',
    });
  });

  it('does not fetch when stepType is empty', async () => {
    await act(async () => {
      renderWithApp(<BusinessRulePolicySelector {...defaultProps} stepType="" />);
    });

    expect(getBusinessRulePolicies).not.toHaveBeenCalled();
  });

  it('clears policy when switching to "none"', async () => {
    const user = userEvent.setup();
    const onPolicyIdChange = vi.fn();

    await act(async () => {
      renderWithApp(
        <BusinessRulePolicySelector
          {...defaultProps}
          policyId={1}
          onPolicyIdChange={onPolicyIdChange}
        />,
      );
    });

    const radios = screen.getAllByRole('radio');
    await user.click(radios[0]); // "Aucune"

    expect(onPolicyIdChange).toHaveBeenCalledWith(null);
  });

  it('shows message when stepType is empty in predefined mode', async () => {
    await act(async () => {
      renderWithApp(
        <BusinessRulePolicySelector
          {...defaultProps}
          stepType=""
          policyId={null}
        />,
      );
    });

    await act(async () => {
      const radios = screen.getAllByRole('radio');
      await userEvent.setup().click(radios[1]); // "Règle prédéfinie"
    });

    expect(
      screen.getByText(/Sélectionnez une intégration.*pour afficher les règles métier/),
    ).toBeInTheDocument();
  });
});

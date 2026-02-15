/**
 * Story 28.4, AC#10: Tests for BusinessRulePolicySelector.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, act } from '@testing-library/react';
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
    inlineJson: '',
    onPolicyIdChange: vi.fn(),
    onInlineJsonChange: vi.fn(),
  };

  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(getBusinessRulePolicies).mockResolvedValue({
      data: mockPolicies,
      pagination: null,
    });
  });

  it('renders three radio options', async () => {
    await act(async () => {
      renderWithApp(<BusinessRulePolicySelector {...defaultProps} />);
    });

    const radios = screen.getAllByRole('radio');
    expect(radios).toHaveLength(3);
  });

  it('defaults to "none" mode when no policy selected', async () => {
    await act(async () => {
      renderWithApp(<BusinessRulePolicySelector {...defaultProps} />);
    });

    const radios = screen.getAllByRole('radio');
    // First radio "Aucune" should be checked
    expect(radios[0]).toBeChecked();
  });

  it('selects "predefined" mode when policyId is set', async () => {
    await act(async () => {
      renderWithApp(
        <BusinessRulePolicySelector {...defaultProps} policyId={1} />,
      );
    });

    const radios = screen.getAllByRole('radio');
    // Second radio "Règle prédéfinie" should be checked
    expect(radios[1]).toBeChecked();
  });

  it('selects "inline" mode when inlineJson is set', async () => {
    await act(async () => {
      renderWithApp(
        <BusinessRulePolicySelector
          {...defaultProps}
          inlineJson='{"on_step_output": []}'
        />,
      );
    });

    const radios = screen.getAllByRole('radio');
    // Third radio "Règle personnalisée" should be checked
    expect(radios[2]).toBeChecked();
  });

  it('shows inline editor when "inline" mode is selected', async () => {
    await act(async () => {
      renderWithApp(
        <BusinessRulePolicySelector
          {...defaultProps}
          inlineJson='{"on_step_output": []}'
        />,
      );
    });

    expect(screen.getByLabelText('Éditeur de règles métier')).toBeInTheDocument();
  });

  it('clears both values when switching to "none"', async () => {
    const user = userEvent.setup();
    const onPolicyIdChange = vi.fn();
    const onInlineJsonChange = vi.fn();

    await act(async () => {
      renderWithApp(
        <BusinessRulePolicySelector
          policyId={1}
          inlineJson=""
          onPolicyIdChange={onPolicyIdChange}
          onInlineJsonChange={onInlineJsonChange}
        />,
      );
    });

    const radios = screen.getAllByRole('radio');
    await user.click(radios[0]); // "Aucune"

    expect(onPolicyIdChange).toHaveBeenCalledWith(null);
    expect(onInlineJsonChange).toHaveBeenCalledWith('');
  });

  it('clears inline when switching to "predefined"', async () => {
    const user = userEvent.setup();
    const onInlineJsonChange = vi.fn();

    await act(async () => {
      renderWithApp(
        <BusinessRulePolicySelector
          policyId={null}
          inlineJson='{"on_step_output": []}'
          onPolicyIdChange={vi.fn()}
          onInlineJsonChange={onInlineJsonChange}
        />,
      );
    });

    const radios = screen.getAllByRole('radio');
    await user.click(radios[1]); // "Règle prédéfinie"

    expect(onInlineJsonChange).toHaveBeenCalledWith('');
  });

  it('clears policyId when switching to "inline"', async () => {
    const user = userEvent.setup();
    const onPolicyIdChange = vi.fn();

    await act(async () => {
      renderWithApp(
        <BusinessRulePolicySelector
          policyId={1}
          inlineJson=""
          onPolicyIdChange={onPolicyIdChange}
          onInlineJsonChange={vi.fn()}
        />,
      );
    });

    const radios = screen.getAllByRole('radio');
    await user.click(radios[2]); // "Règle personnalisée"

    expect(onPolicyIdChange).toHaveBeenCalledWith(null);
  });
});

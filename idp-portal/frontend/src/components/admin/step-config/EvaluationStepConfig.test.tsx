/**
 * Tests for EvaluationStepConfig — Story 57.20, Task 6.
 * Verifies MappingHelpPopover integration (input only) and validation warnings.
 */

import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { EvaluationStepConfig } from './EvaluationStepConfig';

vi.mock('../../../services/business_rules_service', () => ({
  getBusinessRulePolicies: vi.fn().mockResolvedValue({ data: [] }),
}));

const baseData = {
  name: null,
  label: 'Evaluation',
  step_type: 'evaluation' as const,
  step_id: 'eval-1',
  on_success_step_id: null,
  on_error_step_id: null,
  on_success_step_name: null,
  on_error_step_name: null,
  isStartNode: false,
  isEndNode: false,
  policy_id: null,
  input_mapping: null,
};

describe('EvaluationStepConfig — MappingHelpPopover integration (Story 57.20)', () => {
  it('renders input mapping help icon', () => {
    render(<EvaluationStepConfig data={baseData} onUpdate={vi.fn()} />);
    expect(screen.getByLabelText('Aide syntaxe input_mapping')).toBeInTheDocument();
  });

  it('does NOT render output mapping help icon (no output_mapping for evaluation)', () => {
    render(<EvaluationStepConfig data={baseData} onUpdate={vi.fn()} />);
    expect(screen.queryByLabelText('Aide syntaxe output_mapping')).not.toBeInTheDocument();
  });

  it('shows input help content on click', () => {
    render(<EvaluationStepConfig data={baseData} onUpdate={vi.fn()} />);
    fireEvent.click(screen.getByLabelText('Aide syntaxe input_mapping'));
    expect(screen.getByText('Syntaxe input_mapping')).toBeInTheDocument();
  });
});

describe('EvaluationStepConfig — validation warnings (Story 57.20, AC5)', () => {
  it('shows warning for invalid step reference', () => {
    const dataWithBadRef = {
      ...baseData,
      input_mapping: { param: '{{ steps.xyz.field }}' },
    };
    const steps = [{ value: 'step-1', label: 'Étape 1' }];
    render(
      <EvaluationStepConfig data={dataWithBadRef} onUpdate={vi.fn()} availableStepOptions={steps} />
    );
    expect(screen.getByTestId('input-mapping-editor-warning')).toBeInTheDocument();
    expect(screen.getByText(/Référence inconnue : step_id 'xyz'/)).toBeInTheDocument();
  });
});

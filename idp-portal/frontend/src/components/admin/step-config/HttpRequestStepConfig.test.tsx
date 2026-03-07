/**
 * Tests for HttpRequestStepConfig — Story 57.20, Task 6.
 * Verifies MappingHelpPopover integration and validation warnings.
 */

import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { HttpRequestStepConfig } from './HttpRequestStepConfig';

vi.mock('../../../hooks/useOutputSchemas', () => ({
  useOutputSchemas: () => ({ availableVariables: [], loading: false, error: null }),
}));

const baseData = {
  name: null,
  label: 'HTTP Request',
  step_type: 'http_request' as const,
  step_id: 'hr-1',
  on_success_step_id: null,
  on_error_step_id: null,
  on_success_step_name: null,
  on_error_step_name: null,
  isStartNode: false,
  isEndNode: false,
  url: 'https://api.example.com',
  method: 'GET' as const,
  headers: null,
  input_mapping: null,
  output_mapping: null,
  request_timeout: null,
};

describe('HttpRequestStepConfig — MappingHelpPopover integration (Story 57.20)', () => {
  it('renders input mapping help icon', () => {
    render(<HttpRequestStepConfig data={baseData} onUpdate={vi.fn()} />);
    expect(screen.getByLabelText('Aide syntaxe input_mapping')).toBeInTheDocument();
  });

  it('renders output mapping help icon', () => {
    render(<HttpRequestStepConfig data={baseData} onUpdate={vi.fn()} />);
    expect(screen.getByLabelText('Aide syntaxe output_mapping')).toBeInTheDocument();
  });

  it('shows output help content with http_request outputs on click', () => {
    render(<HttpRequestStepConfig data={baseData} onUpdate={vi.fn()} />);
    fireEvent.click(screen.getByLabelText('Aide syntaxe output_mapping'));
    expect(screen.getByText('body')).toBeInTheDocument();
    expect(screen.getByText('status_code')).toBeInTheDocument();
  });
});

describe('HttpRequestStepConfig — validation warnings (Story 57.20, AC5)', () => {
  it('shows warning for invalid step reference in params', () => {
    const dataWithBadRef = {
      ...baseData,
      input_mapping: { q: '{{ steps.bad_step.value }}' },
    };
    const steps = [{ value: 'step-1', label: 'Étape 1' }];
    render(
      <HttpRequestStepConfig data={dataWithBadRef} onUpdate={vi.fn()} availableStepOptions={steps} />
    );
    expect(screen.getByTestId('params-editor-warning')).toBeInTheDocument();
    expect(screen.getByText(/Référence inconnue : step_id 'bad_step'/)).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Story 63.3 — VariablePicker intégration
// ---------------------------------------------------------------------------

const dataWithMapping = { ...baseData, input_mapping: { param1: 'value1' } };

describe('HttpRequestStepConfig — VariablePicker (Story 63.3)', () => {
  it('passe workflowId au composant enfant via KeyValueEditor', () => {
    const { container } = render(
      <HttpRequestStepConfig
        data={dataWithMapping}
        onUpdate={vi.fn()}
        workflowId={42}
        availableStepIds={['hr-1', 'hr-2']}
      />
    );
    expect(container.querySelector('[data-testid="variable-picker-trigger"]')).toBeInTheDocument();
  });

  it('ne rend pas le VariablePicker si workflowId est undefined', () => {
    const { container } = render(
      <HttpRequestStepConfig data={dataWithMapping} onUpdate={vi.fn()} />
    );
    expect(container.querySelector('[data-testid="variable-picker-trigger"]')).not.toBeInTheDocument();
  });
});

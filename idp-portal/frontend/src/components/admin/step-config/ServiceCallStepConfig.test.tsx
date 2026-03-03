/**
 * Tests for ServiceCallStepConfig — Story 57.20, Task 6.
 * Verifies MappingHelpPopover integration, updated placeholders, and validation warnings.
 */

import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { ServiceCallStepConfig } from './ServiceCallStepConfig';

const baseData = {
  name: null,
  label: 'Service Call',
  step_type: 'service_call' as const,
  step_id: 'sc-1',
  on_success_step_id: null,
  on_error_step_id: null,
  on_success_step_name: null,
  on_error_step_name: null,
  isStartNode: false,
  isEndNode: false,
  integration_type: 'servicenow',
  operation: 'create_change',
  input_mapping: null,
  output_mapping: null,
};

describe('ServiceCallStepConfig — MappingHelpPopover integration (Story 57.20)', () => {
  it('renders input mapping help icon', () => {
    render(<ServiceCallStepConfig data={baseData} onUpdate={vi.fn()} />);
    expect(screen.getByLabelText('Aide syntaxe input_mapping')).toBeInTheDocument();
  });

  it('renders output mapping help icon', () => {
    render(<ServiceCallStepConfig data={baseData} onUpdate={vi.fn()} />);
    expect(screen.getByLabelText('Aide syntaxe output_mapping')).toBeInTheDocument();
  });

  it('shows input help content with available steps on click', () => {
    const steps = [
      { value: 'step-1', label: 'Étape 1 — Discovery' },
    ];
    render(<ServiceCallStepConfig data={baseData} onUpdate={vi.fn()} availableStepOptions={steps} />);
    fireEvent.click(screen.getByLabelText('Aide syntaxe input_mapping'));
    expect(screen.getByText('Syntaxe input_mapping')).toBeInTheDocument();
    expect(screen.getByText('Étape 1 — Discovery')).toBeInTheDocument();
  });

  it('shows output help content with service_call outputs on click', () => {
    render(<ServiceCallStepConfig data={baseData} onUpdate={vi.fn()} />);
    fireEvent.click(screen.getByLabelText('Aide syntaxe output_mapping'));
    expect(screen.getByText('Syntaxe output_mapping')).toBeInTheDocument();
    expect(screen.getByText('number')).toBeInTheDocument();
    expect(screen.getByText('sys_id')).toBeInTheDocument();
  });

  it('uses updated placeholder for input_mapping value', () => {
    render(<ServiceCallStepConfig data={baseData} onUpdate={vi.fn()} />);
    expect(screen.getByText("Mapping d'entrée (input_mapping)")).toBeInTheDocument();
  });

  it('uses updated placeholder for output_mapping value', () => {
    render(<ServiceCallStepConfig data={baseData} onUpdate={vi.fn()} />);
    expect(screen.getByText('Mapping de sortie (output_mapping)')).toBeInTheDocument();
  });
});

describe('ServiceCallStepConfig — validation warnings (Story 57.20, AC5)', () => {
  it('shows warning for invalid step reference', () => {
    const dataWithBadRef = {
      ...baseData,
      input_mapping: { param1: '{{ steps.nonexistent.field }}' },
    };
    const steps = [{ value: 'step-1', label: 'Étape 1' }];
    render(
      <ServiceCallStepConfig data={dataWithBadRef} onUpdate={vi.fn()} availableStepOptions={steps} />
    );
    expect(screen.getByTestId('input-mapping-editor-warning')).toBeInTheDocument();
    expect(screen.getByText(/Référence inconnue : step_id 'nonexistent'/)).toBeInTheDocument();
  });

  it('does not show warning when references are valid', () => {
    const dataWithGoodRef = {
      ...baseData,
      input_mapping: { param1: '{{ steps.step-1.field }}' },
    };
    const steps = [{ value: 'step-1', label: 'Étape 1' }];
    render(
      <ServiceCallStepConfig data={dataWithGoodRef} onUpdate={vi.fn()} availableStepOptions={steps} />
    );
    expect(screen.queryByTestId('input-mapping-editor-warning')).not.toBeInTheDocument();
  });

  it('does not show warning when no template references exist', () => {
    const dataWithPlain = {
      ...baseData,
      input_mapping: { param1: 'plain value' },
    };
    const steps = [{ value: 'step-1', label: 'Étape 1' }];
    render(
      <ServiceCallStepConfig data={dataWithPlain} onUpdate={vi.fn()} availableStepOptions={steps} />
    );
    expect(screen.queryByTestId('input-mapping-editor-warning')).not.toBeInTheDocument();
  });
});

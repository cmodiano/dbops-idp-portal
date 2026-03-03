import { describe, it, expect } from 'vitest';
import { getStepLabel, getStepOptions, type StepLabelInput } from './workflowStepLabels';

describe('getStepLabel', () => {
  it('returns name when name is defined', () => {
    const step: StepLabelInput = { name: 'Mon étape custom', order: 1, step_type: 'platform', action_name: 'Deploy' };
    expect(getStepLabel(step)).toBe('Mon étape custom');
  });

  it('generates label for platform step with action_name', () => {
    const step: StepLabelInput = { name: null, order: 2, step_type: 'platform', action_name: 'Deploy App' };
    expect(getStepLabel(step)).toBe('Étape 2 — Deploy App');
  });

  it('generates label for platform step without action_name', () => {
    const step: StepLabelInput = { name: null, order: 3, step_type: 'platform' };
    expect(getStepLabel(step)).toBe('Étape 3');
  });

  it('generates label for service_call step', () => {
    const step: StepLabelInput = { name: null, order: 1, step_type: 'service_call', integration_type: 'servicenow', operation: 'create_change' };
    expect(getStepLabel(step)).toBe('Étape 1 — servicenow / create_change');
  });

  it('generates label for service_call step with defaults', () => {
    const step: StepLabelInput = { name: null, order: 2, step_type: 'service_call' };
    expect(getStepLabel(step)).toBe('Étape 2 — service / ?');
  });

  it('generates label for evaluation step', () => {
    const step: StepLabelInput = { name: null, order: 1, step_type: 'evaluation', policy_id: 42 };
    expect(getStepLabel(step)).toBe('Étape 1 — Évaluation policy #42');
  });

  it('generates label for evaluation step without policy_id', () => {
    const step: StepLabelInput = { name: null, order: 1, step_type: 'evaluation' };
    expect(getStepLabel(step)).toBe('Étape 1 — Évaluation policy #?');
  });

  it('generates label for gate step with approval', () => {
    const step: StepLabelInput = { name: null, order: 3, step_type: 'gate', gate_type: 'approval' };
    expect(getStepLabel(step)).toBe('Étape 3 — Approbation');
  });

  it('generates label for gate step with maintenance_window', () => {
    const step: StepLabelInput = { name: null, order: 4, step_type: 'gate', gate_type: 'maintenance_window' };
    expect(getStepLabel(step)).toBe('Étape 4 — Fenêtre maintenance');
  });

  it('generates label for gate step without gate_type', () => {
    const step: StepLabelInput = { name: null, order: 5, step_type: 'gate' };
    expect(getStepLabel(step)).toBe('Étape 5 — Fenêtre maintenance');
  });

  it('generates label for http_request step', () => {
    const step: StepLabelInput = { name: null, order: 2, step_type: 'http_request', method: 'POST', url: 'https://api.example.com/webhook' };
    expect(getStepLabel(step)).toBe('Étape 2 — POST https://api.example.com/webhook');
  });

  it('generates label for http_request step with defaults', () => {
    const step: StepLabelInput = { name: null, order: 1, step_type: 'http_request' };
    expect(getStepLabel(step)).toBe('Étape 1 — GET');
  });

  it('generates label for schedule_execution step with action_name', () => {
    const step: StepLabelInput = { name: null, order: 1, step_type: 'schedule_execution', action_name: 'Backup DB' };
    expect(getStepLabel(step)).toBe('Étape 1 — Planifier Backup DB');
  });

  it('generates label for schedule_execution step without action_name', () => {
    const step: StepLabelInput = { name: null, order: 2, step_type: 'schedule_execution' };
    expect(getStepLabel(step)).toBe('Étape 2 — Planification');
  });

  it('generates label without order', () => {
    const step: StepLabelInput = { name: null, step_type: 'platform', action_name: 'Deploy' };
    expect(getStepLabel(step)).toBe('Étape — Deploy');
  });

  it('generates fallback label for unknown step_type', () => {
    const step: StepLabelInput = { name: null, order: 1, step_type: 'unknown_type' as string };
    expect(getStepLabel(step)).toBe('Étape 1');
  });

  it('generates fallback label for step without step_type', () => {
    const step: StepLabelInput = { name: null, order: 1 };
    expect(getStepLabel(step)).toBe('Étape 1');
  });
});

describe('getStepOptions', () => {
  const steps = [
    { step_id: 'uuid-1', name: null, order: 1, step_type: 'platform' as const, action_name: 'Deploy' },
    { step_id: 'uuid-2', name: 'Custom Gate', order: 2, step_type: 'gate' as const, gate_type: 'approval' as const },
    { step_id: 'uuid-3', name: null, order: 3, step_type: 'evaluation' as const, policy_id: 5 },
  ];

  it('returns options with labels for all steps', () => {
    const options = getStepOptions(steps);
    expect(options).toEqual([
      { value: 'uuid-1', label: 'Étape 1 — Deploy' },
      { value: 'uuid-2', label: 'Custom Gate' },
      { value: 'uuid-3', label: 'Étape 3 — Évaluation policy #5' },
    ]);
  });

  it('excludes the specified step_id', () => {
    const options = getStepOptions(steps, 'uuid-2');
    expect(options).toHaveLength(2);
    expect(options.map((o) => o.value)).toEqual(['uuid-1', 'uuid-3']);
  });

  it('filters out steps without step_id', () => {
    const stepsWithNull = [
      { step_id: 'uuid-1', name: null, order: 1, step_type: 'platform' as const, action_name: 'Deploy' },
      { step_id: null, name: null, order: 2, step_type: 'platform' as const },
    ];
    const options = getStepOptions(stepsWithNull);
    expect(options).toHaveLength(1);
  });

  it('returns empty array for empty input', () => {
    expect(getStepOptions([])).toEqual([]);
  });
});

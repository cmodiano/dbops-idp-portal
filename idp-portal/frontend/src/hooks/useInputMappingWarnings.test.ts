/**
 * Tests for useInputMappingWarnings hook (Story 71.11, AC #3).
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook } from '@testing-library/react';
import { useInputMappingWarnings } from './useInputMappingWarnings';
import * as validateModule from '../utils/validateStepReferences';

describe('useInputMappingWarnings', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('retourne [] si inputMapping est null', () => {
    const { result } = renderHook(() =>
      useInputMappingWarnings(null, [{ value: 'step1', label: 'Step 1' }]),
    );
    expect(result.current).toEqual([]);
  });

  it('retourne [] si availableStepOptions est undefined', () => {
    const { result } = renderHook(() =>
      useInputMappingWarnings({ key: '{{ steps.step1.output }}' }, undefined),
    );
    expect(result.current).toEqual([]);
  });

  it('retourne un warning pour un step_id inconnu', () => {
    vi.spyOn(validateModule, 'validateStepReferences').mockReturnValue(['unknown-step']);

    const { result } = renderHook(() =>
      useInputMappingWarnings(
        { param: '{{ steps.unknown-step.output }}' },
        [{ value: 'step1', label: 'Step 1' }],
      ),
    );

    expect(result.current).toHaveLength(1);
    expect(result.current[0]).toContain('unknown-step');
  });

  it('déduplique les warnings identiques (même step_id dans plusieurs valeurs)', () => {
    vi.spyOn(validateModule, 'validateStepReferences').mockReturnValue(['missing-step']);

    const { result } = renderHook(() =>
      useInputMappingWarnings(
        {
          param1: '{{ steps.missing-step.output }}',
          param2: '{{ steps.missing-step.other }}',
        },
        [{ value: 'step1', label: 'Step 1' }],
      ),
    );

    // Both values reference missing-step but should produce only 1 unique warning
    expect(result.current).toHaveLength(1);
  });

  it('retourne [] si tous les step_ids sont valides', () => {
    vi.spyOn(validateModule, 'validateStepReferences').mockReturnValue([]);

    const { result } = renderHook(() =>
      useInputMappingWarnings(
        { param: '{{ steps.step1.output }}' },
        [{ value: 'step1', label: 'Step 1' }],
      ),
    );

    expect(result.current).toEqual([]);
  });
});

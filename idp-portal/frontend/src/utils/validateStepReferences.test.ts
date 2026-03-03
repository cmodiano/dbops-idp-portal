/**
 * Tests for validateStepReferences — Story 57.20, Task 4.
 */

import { describe, it, expect } from 'vitest';
import { extractStepReferences, validateStepReferences } from './validateStepReferences';

describe('extractStepReferences', () => {
  it('extracts a single step_id from a template', () => {
    expect(extractStepReferences('{{ steps.discovery.databases }}')).toEqual(['discovery']);
  });

  it('extracts multiple distinct step_ids', () => {
    const value = '{{ steps.step1.field1 }} and {{ steps.step2.field2 }}';
    expect(extractStepReferences(value)).toEqual(['step1', 'step2']);
  });

  it('deduplicates step_ids', () => {
    const value = '{{ steps.abc.x }} {{ steps.abc.y }}';
    expect(extractStepReferences(value)).toEqual(['abc']);
  });

  it('returns empty array when no template references', () => {
    expect(extractStepReferences('just a plain string')).toEqual([]);
  });

  it('returns empty array for empty string', () => {
    expect(extractStepReferences('')).toEqual([]);
  });

  it('handles UUIDs as step_ids', () => {
    expect(extractStepReferences('{{ steps.abc-123-def.field }}')).toEqual(['abc-123-def']);
  });

  it('handles underscores in step_ids', () => {
    expect(extractStepReferences('{{ steps.my_step.field }}')).toEqual(['my_step']);
  });

  it('handles extra whitespace in templates', () => {
    expect(extractStepReferences('{{  steps.spaced.field  }}')).toEqual(['spaced']);
  });

  it('handles templates with filters', () => {
    const value = "{{ steps.discovery.databases | join(', ') }}";
    expect(extractStepReferences(value)).toEqual(['discovery']);
  });
});

describe('validateStepReferences', () => {
  const availableStepIds = ['step-aaa', 'step-bbb', 'step-ccc'];

  it('returns empty array when all references are valid', () => {
    const value = '{{ steps.step-aaa.field }}';
    expect(validateStepReferences(value, availableStepIds)).toEqual([]);
  });

  it('returns invalid step_ids', () => {
    const value = '{{ steps.unknown.field }}';
    expect(validateStepReferences(value, availableStepIds)).toEqual(['unknown']);
  });

  it('returns only invalid step_ids when mixed', () => {
    const value = '{{ steps.step-aaa.x }} {{ steps.invalid.y }}';
    expect(validateStepReferences(value, availableStepIds)).toEqual(['invalid']);
  });

  it('returns multiple invalid step_ids', () => {
    const value = '{{ steps.bad1.x }} {{ steps.bad2.y }}';
    expect(validateStepReferences(value, availableStepIds)).toEqual(['bad1', 'bad2']);
  });

  it('returns empty array for plain text without references', () => {
    expect(validateStepReferences('no template', availableStepIds)).toEqual([]);
  });
});

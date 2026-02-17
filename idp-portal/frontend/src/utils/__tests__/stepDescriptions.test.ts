import { describe, it, expect } from 'vitest';
import { STEP_DESCRIPTIONS_SIMPLIFIED } from '../stepDescriptions';

describe('STEP_DESCRIPTIONS_SIMPLIFIED', () => {
  it('has exactly 3 descriptions for target, parameters, and confirmation steps', () => {
    expect(STEP_DESCRIPTIONS_SIMPLIFIED).toHaveLength(3);
  });

  it('contains non-empty strings for each step', () => {
    for (const desc of STEP_DESCRIPTIONS_SIMPLIFIED) {
      expect(typeof desc).toBe('string');
      expect(desc.length).toBeGreaterThan(0);
    }
  });

  it('has target selection as first description', () => {
    expect(STEP_DESCRIPTIONS_SIMPLIFIED[0]).toContain('cible');
  });

  it('has parameters as second description', () => {
    expect(STEP_DESCRIPTIONS_SIMPLIFIED[1]).toContain('obligatoires');
  });

  it('has confirmation as third description', () => {
    expect(STEP_DESCRIPTIONS_SIMPLIFIED[2]).toContain('correct');
  });
});

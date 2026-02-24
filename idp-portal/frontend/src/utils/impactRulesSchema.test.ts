/**
 * Unit tests for impact rules JSON ↔ list conversion (Story 2.18, Task 1.2).
 */

import { describe, it, expect } from 'vitest';
import { impactRulesToList, listToImpactRules } from './impactRulesSchema';
import type { ImpactRuleDefinition } from '../types/api';
import type { ImpactRulesJson } from './impactRulesSchema';

describe('impactRulesToList', () => {
  it('returns empty array for null or undefined', () => {
    expect(impactRulesToList(null)).toEqual([]);
    expect(impactRulesToList(undefined)).toEqual([]);
  });

  it('returns empty array for empty object', () => {
    expect(impactRulesToList({})).toEqual([]);
  });

  it('converts impact_rules object to ImpactRuleDefinition list', () => {
    const rules: ImpactRulesJson = {
      DEV: { level: 'low', criteria: 'Environnement de developpement isole' },
      PROD: { level: 'high', criteria: 'Environnement de production' },
    };
    const list = impactRulesToList(rules);
    expect(list).toHaveLength(2);

    const devRule = list.find((r) => r.environment === 'DEV');
    expect(devRule).toBeDefined();
    expect(devRule?.level).toBe('low');
    expect(devRule?.criteria).toBe('Environnement de developpement isole');
    expect(devRule?.id).toBeDefined();

    const prodRule = list.find((r) => r.environment === 'PROD');
    expect(prodRule).toBeDefined();
    expect(prodRule?.level).toBe('high');
    expect(prodRule?.criteria).toBe('Environnement de production');
  });

  it('handles missing criteria (null)', () => {
    const rules: ImpactRulesJson = {
      DEV: { level: 'medium' },
    };
    const list = impactRulesToList(rules);
    expect(list).toHaveLength(1);
    expect(list[0].criteria).toBeNull();
  });

  it('defaults to low for invalid level', () => {
    const rules = {
      DEV: { level: 'invalid_level' },
    } as unknown as ImpactRulesJson;
    const list = impactRulesToList(rules);
    expect(list[0].level).toBe('low');
  });

  it('handles all valid levels', () => {
    const rules: ImpactRulesJson = {
      DEV: { level: 'low' },
      STAGING: { level: 'medium' },
      PROD: { level: 'high' },
      CRITICAL_ENV: { level: 'critical' },
    };
    const list = impactRulesToList(rules);
    expect(list.find((r) => r.environment === 'DEV')?.level).toBe('low');
    expect(list.find((r) => r.environment === 'STAGING')?.level).toBe('medium');
    expect(list.find((r) => r.environment === 'PROD')?.level).toBe('high');
    expect(list.find((r) => r.environment === 'CRITICAL_ENV')?.level).toBe('critical');
  });
});

describe('listToImpactRules', () => {
  it('returns null for empty list', () => {
    expect(listToImpactRules([])).toBeNull();
  });

  it('converts ImpactRuleDefinition list to impact_rules object', () => {
    const list: ImpactRuleDefinition[] = [
      { environment: 'DEV', level: 'low', criteria: 'Dev env' },
      { environment: 'PROD', level: 'high', criteria: 'Production' },
    ];
    const rules = listToImpactRules(list);
    expect(rules).not.toBeNull();
    expect(rules?.DEV).toEqual({ level: 'low', criteria: 'Dev env' });
    expect(rules?.PROD).toEqual({ level: 'high', criteria: 'Production' });
  });

  it('omits criteria when null or empty', () => {
    const list: ImpactRuleDefinition[] = [
      { environment: 'DEV', level: 'low', criteria: null },
      { environment: 'STAGING', level: 'medium', criteria: '' },
      { environment: 'PROD', level: 'high', criteria: '   ' },
    ];
    const rules = listToImpactRules(list);
    expect(rules?.DEV).toEqual({ level: 'low' });
    expect(rules?.STAGING).toEqual({ level: 'medium' });
    expect(rules?.PROD).toEqual({ level: 'high' });
  });

  it('skips rules with empty environment', () => {
    const list: ImpactRuleDefinition[] = [
      { environment: '', level: 'low', criteria: null },
      { environment: 'DEV', level: 'medium', criteria: null },
    ];
    const rules = listToImpactRules(list);
    expect(rules).not.toBeNull();
    expect(Object.keys(rules!)).toEqual(['DEV']);
  });

  it('trims environment and criteria whitespace', () => {
    const list: ImpactRuleDefinition[] = [
      { environment: '  DEV  ', level: 'low', criteria: '  test  ' },
    ];
    const rules = listToImpactRules(list);
    expect(rules?.DEV).toEqual({ level: 'low', criteria: 'test' });
  });
});

describe('round-trip conversion', () => {
  it('rules -> list -> rules preserves data', () => {
    const original: ImpactRulesJson = {
      DEV: { level: 'low', criteria: 'Dev environment' },
      STAGING: { level: 'medium', criteria: 'Staging environment' },
      PROD: { level: 'high', criteria: 'Production environment' },
    };
    const list = impactRulesToList(original);
    const back = listToImpactRules(list);
    expect(back).toEqual(original);
  });

  it('list -> rules -> list preserves data (without ids)', () => {
    const original: ImpactRuleDefinition[] = [
      { environment: 'DEV', level: 'low', criteria: 'Dev' },
      { environment: 'PROD', level: 'critical', criteria: null },
    ];
    const rules = listToImpactRules(original);
    const back = impactRulesToList(rules);

    // Compare without ids
    const withoutIds = back.map(({ id: _, ...rest }) => rest);
    const originalWithoutIds = original.map(({ id: _, ...rest }) => rest);
    expect(withoutIds).toEqual(originalWithoutIds);
  });
});

describe('empty impact_rules round-trip (Issue #4)', () => {
  it('null input produces empty list, empty list produces null', () => {
    const list = impactRulesToList(null);
    expect(list).toEqual([]);
    const back = listToImpactRules(list);
    expect(back).toBeNull();
  });

  it('empty object input produces empty list, empty list produces null', () => {
    const list = impactRulesToList({});
    expect(list).toEqual([]);
    const back = listToImpactRules(list);
    expect(back).toBeNull();
  });

  it('undefined input produces empty list', () => {
    const list = impactRulesToList(undefined);
    expect(list).toEqual([]);
  });
});

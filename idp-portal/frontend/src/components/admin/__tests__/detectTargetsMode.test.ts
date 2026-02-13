/**
 * Tests for detectTargetsMode helper (Story 23.7, Task 2).
 * Covers: all, oracle, sql, list, pattern, advanced cases.
 */

import { describe, it, expect } from 'vitest';
import { detectTargetsMode } from '../ProfileForm';
import type { ProfileTargetPermissionsResponse } from '../../../types/api';

describe('detectTargetsMode (Story 23.7)', () => {
  it('returns "all" when targets_type is all and no filter', () => {
    const perms: ProfileTargetPermissionsResponse = {
      targets_type: 'all',
      target_names: [],
      target_patterns: [],
      filter_by_attribute: null,
    };
    expect(detectTargetsMode(perms)).toBe('all');
  });

  it('returns "all" when targets_type is all and filter_by_attribute is undefined', () => {
    const perms: ProfileTargetPermissionsResponse = {
      targets_type: 'all',
      target_names: [],
      target_patterns: [],
    };
    expect(detectTargetsMode(perms)).toBe('all');
  });

  it('returns "all-oracle" when filter_by_attribute is { engine_type: ["oracle"] }', () => {
    const perms: ProfileTargetPermissionsResponse = {
      targets_type: 'all',
      target_names: [],
      target_patterns: [],
      filter_by_attribute: { engine_type: ['oracle'] },
    };
    expect(detectTargetsMode(perms)).toBe('all-oracle');
  });

  it('returns "all-oracle" case-insensitive (Oracle)', () => {
    const perms: ProfileTargetPermissionsResponse = {
      targets_type: 'all',
      target_names: [],
      target_patterns: [],
      filter_by_attribute: { engine_type: ['Oracle'] },
    };
    expect(detectTargetsMode(perms)).toBe('all-oracle');
  });

  it('returns "all-sql" when filter_by_attribute is { engine_type: ["sqlserver"] }', () => {
    const perms: ProfileTargetPermissionsResponse = {
      targets_type: 'all',
      target_names: [],
      target_patterns: [],
      filter_by_attribute: { engine_type: ['sqlserver'] },
    };
    expect(detectTargetsMode(perms)).toBe('all-sql');
  });

  it('returns "all-sql" case-insensitive (SQLSERVER)', () => {
    const perms: ProfileTargetPermissionsResponse = {
      targets_type: 'all',
      target_names: [],
      target_patterns: [],
      filter_by_attribute: { engine_type: ['SQLSERVER'] },
    };
    expect(detectTargetsMode(perms)).toBe('all-sql');
  });

  it('returns "list" when targets_type is list', () => {
    const perms: ProfileTargetPermissionsResponse = {
      targets_type: 'list',
      target_names: ['srv-01'],
      target_patterns: [],
      filter_by_attribute: null,
    };
    expect(detectTargetsMode(perms)).toBe('list');
  });

  it('returns "pattern" when targets_type is pattern', () => {
    const perms: ProfileTargetPermissionsResponse = {
      targets_type: 'pattern',
      target_names: [],
      target_patterns: ['srv-*'],
      filter_by_attribute: null,
    };
    expect(detectTargetsMode(perms)).toBe('pattern');
  });

  it('returns "advanced" for multi-value engine_type', () => {
    const perms: ProfileTargetPermissionsResponse = {
      targets_type: 'all',
      target_names: [],
      target_patterns: [],
      filter_by_attribute: { engine_type: ['oracle', 'sqlserver'] },
    };
    expect(detectTargetsMode(perms)).toBe('advanced');
  });

  it('returns "advanced" for unsupported key (zone)', () => {
    const perms: ProfileTargetPermissionsResponse = {
      targets_type: 'all',
      target_names: [],
      target_patterns: [],
      filter_by_attribute: { zone: ['prod'] },
    };
    expect(detectTargetsMode(perms)).toBe('advanced');
  });

  it('returns "advanced" for multi-key filter', () => {
    const perms: ProfileTargetPermissionsResponse = {
      targets_type: 'all',
      target_names: [],
      target_patterns: [],
      filter_by_attribute: { engine_type: ['oracle'], zone: ['prod'] },
    };
    expect(detectTargetsMode(perms)).toBe('advanced');
  });

  it('returns "advanced" for unknown engine_type value', () => {
    const perms: ProfileTargetPermissionsResponse = {
      targets_type: 'all',
      target_names: [],
      target_patterns: [],
      filter_by_attribute: { engine_type: ['postgres'] },
    };
    expect(detectTargetsMode(perms)).toBe('advanced');
  });

  it('returns "all" for empty filter_by_attribute object', () => {
    const perms: ProfileTargetPermissionsResponse = {
      targets_type: 'all',
      target_names: [],
      target_patterns: [],
      filter_by_attribute: {},
    };
    expect(detectTargetsMode(perms)).toBe('all');
  });

  it('returns "all-sql" for "sql" engine_type (lowercase)', () => {
    const perms: ProfileTargetPermissionsResponse = {
      targets_type: 'all',
      target_names: [],
      target_patterns: [],
      filter_by_attribute: { engine_type: ['sql'] },
    };
    expect(detectTargetsMode(perms)).toBe('all-sql');
  });

  it('returns "advanced" for filter_by_attribute with undefined engine_type array', () => {
    const perms: ProfileTargetPermissionsResponse = {
      targets_type: 'all',
      target_names: [],
      target_patterns: [],
      filter_by_attribute: { engine_type: undefined as any },
    };
    expect(detectTargetsMode(perms)).toBe('advanced');
  });
});

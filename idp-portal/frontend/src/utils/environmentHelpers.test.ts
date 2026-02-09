import { describe, it, expect } from 'vitest';
import {
  getEnvironmentLabel,
  getEnvironmentColor,
  sortEnvironments,
  isProductionEnvironment,
} from './environmentHelpers';

describe('environmentHelpers', () => {
  describe('getEnvironmentLabel', () => {
    it('returns mapped label for standard environments', () => {
      expect(getEnvironmentLabel('dev')).toBe('Développement');
      expect(getEnvironmentLabel('staging')).toBe('Staging');
      expect(getEnvironmentLabel('prod')).toBe('Production');
    });

    it('capitalizes non-standard environments', () => {
      expect(getEnvironmentLabel('lab')).toBe('Lab');
      expect(getEnvironmentLabel('qa')).toBe('Qa');
      expect(getEnvironmentLabel('uat')).toBe('Uat');
      expect(getEnvironmentLabel('certif')).toBe('Certif');
    });

    it('handles uppercase input', () => {
      expect(getEnvironmentLabel('DEV')).toBe('Développement');
      expect(getEnvironmentLabel('LAB')).toBe('Lab');
      expect(getEnvironmentLabel('PROD')).toBe('Production');
    });

    it('handles mixed case input', () => {
      expect(getEnvironmentLabel('Dev')).toBe('Développement');
      expect(getEnvironmentLabel('Staging')).toBe('Staging');
    });
  });

  describe('getEnvironmentColor', () => {
    it('returns correct color for standard environments', () => {
      expect(getEnvironmentColor('dev')).toBe('success');
      expect(getEnvironmentColor('staging')).toBe('warning');
      expect(getEnvironmentColor('prod')).toBe('error');
    });

    it('returns default color for non-standard environments', () => {
      expect(getEnvironmentColor('lab')).toBe('default');
      expect(getEnvironmentColor('qa')).toBe('default');
      expect(getEnvironmentColor('uat')).toBe('default');
    });

    it('handles uppercase input', () => {
      expect(getEnvironmentColor('DEV')).toBe('success');
      expect(getEnvironmentColor('PROD')).toBe('error');
    });
  });

  describe('sortEnvironments', () => {
    it('sorts with dev, staging, prod first then alphabetical', () => {
      const input = ['qa', 'dev', 'prod', 'lab', 'staging'];
      expect(sortEnvironments(input)).toEqual(['dev', 'staging', 'prod', 'lab', 'qa']);
    });

    it('sorts alphabetically when no standard envs', () => {
      const input = ['uat', 'lab', 'qa'];
      expect(sortEnvironments(input)).toEqual(['lab', 'qa', 'uat']);
    });

    it('handles missing standard environments', () => {
      const input = ['qa', 'dev', 'lab'];
      expect(sortEnvironments(input)).toEqual(['dev', 'lab', 'qa']);
    });

    it('handles only standard environments', () => {
      const input = ['prod', 'dev', 'staging'];
      expect(sortEnvironments(input)).toEqual(['dev', 'staging', 'prod']);
    });

    it('does not mutate original array', () => {
      const input = ['prod', 'dev'];
      sortEnvironments(input);
      expect(input).toEqual(['prod', 'dev']);
    });

    it('handles single element', () => {
      expect(sortEnvironments(['lab'])).toEqual(['lab']);
    });

    it('handles empty array', () => {
      expect(sortEnvironments([])).toEqual([]);
    });
  });

  describe('isProductionEnvironment', () => {
    it('returns true for prod variations', () => {
      expect(isProductionEnvironment('prod')).toBe(true);
      expect(isProductionEnvironment('PROD')).toBe(true);
      expect(isProductionEnvironment('Prod')).toBe(true);
      expect(isProductionEnvironment('production')).toBe(true);
      expect(isProductionEnvironment('PRODUCTION')).toBe(true);
    });

    it('returns false for non-production environments', () => {
      expect(isProductionEnvironment('dev')).toBe(false);
      expect(isProductionEnvironment('staging')).toBe(false);
      expect(isProductionEnvironment('lab')).toBe(false);
      expect(isProductionEnvironment('qa')).toBe(false);
    });
  });
});

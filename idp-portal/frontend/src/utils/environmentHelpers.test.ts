import { describe, it, expect } from 'vitest';
import {
  getEnvironmentLabel,
  getEnvironmentColor,
  getEnvironmentHexColor,
  sortEnvironments,
  isProductionEnvironment,
  normalizeEnvironmentStats,
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

  describe('getEnvironmentHexColor', () => {
    it('returns hex for standard and inventory env values', () => {
      expect(getEnvironmentHexColor('dev')).toBe('#3B82F6');
      expect(getEnvironmentHexColor('developpement')).toBe('#3B82F6');
      expect(getEnvironmentHexColor('staging')).toBe('#F97316');
      expect(getEnvironmentHexColor('certification')).toBe('#F97316');
      expect(getEnvironmentHexColor('prod')).toBe('#EF4444');
      expect(getEnvironmentHexColor('production')).toBe('#EF4444');
    });

    it('returns gray for unknown environments', () => {
      expect(getEnvironmentHexColor('unknown')).toBe('#6B7280');
      expect(getEnvironmentHexColor('custom-env')).toBe('#6B7280');
    });

    it('handles uppercase input', () => {
      expect(getEnvironmentHexColor('DEV')).toBe('#3B82F6');
      expect(getEnvironmentHexColor('PRODUCTION')).toBe('#EF4444');
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

  describe('normalizeEnvironmentStats', () => {
    it('merges DEV and dev into single dev bucket', () => {
      const stats = [
        { environment: 'DEV', count: 70, success_rate: 90 },
        { environment: 'dev', count: 10, success_rate: 100 },
      ];
      const result = normalizeEnvironmentStats(stats);
      expect(result).toHaveLength(1);
      expect(result[0].environment).toBe('dev');
      expect(result[0].count).toBe(80);
      expect(result[0].success_rate).toBe(91.3); // weighted: (70*90 + 10*100) / 80
    });

    it('merges STAGING and staging into single bucket', () => {
      const stats = [
        { environment: 'STAGING', count: 55, success_rate: 85 },
        { environment: 'staging', count: 5, success_rate: 80 },
      ];
      const result = normalizeEnvironmentStats(stats);
      expect(result).toHaveLength(1);
      expect(result[0].environment).toBe('staging');
      expect(result[0].count).toBe(60);
    });

    it('sorts result by canonical order (dev, staging, prod)', () => {
      const stats = [
        { environment: 'prod', count: 5, success_rate: 95 },
        { environment: 'dev', count: 70, success_rate: 90 },
        { environment: 'staging', count: 55, success_rate: 85 },
      ];
      const result = normalizeEnvironmentStats(stats);
      expect(result.map((r) => r.environment)).toEqual(['dev', 'staging', 'prod']);
    });

    it('handles null success_rate', () => {
      const stats = [
        { environment: 'dev', count: 10, success_rate: null },
        { environment: 'DEV', count: 5, success_rate: 100 },
      ];
      const result = normalizeEnvironmentStats(stats);
      expect(result).toHaveLength(1);
      expect(result[0].count).toBe(15);
      // Only row with success_rate contributes to weighted avg: 5*100/5 = 100
      expect(result[0].success_rate).toBe(100);
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

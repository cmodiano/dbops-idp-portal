/**
 * Tests for business_rules_service (Story 71.11, AC #1).
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import {
  getBusinessRulePolicies,
  getBusinessRulePolicy,
  createBusinessRulePolicy,
  updateBusinessRulePolicy,
  deleteBusinessRulePolicy,
} from './business_rules_service';
import * as apiClient from './api_client';

describe('business_rules_service', () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  describe('getBusinessRulePolicies', () => {
    it('calls apiFetchRaw on /admin/business-rule-policies/ without filters', async () => {
      const mockResponse = { count: 0, results: [] };
      vi.spyOn(apiClient, 'apiFetchRaw').mockResolvedValue(mockResponse as any);

      const result = await getBusinessRulePolicies();

      expect(apiClient.apiFetchRaw).toHaveBeenCalledWith('/admin/business-rule-policies/');
      expect(result).toEqual(mockResponse);
    });

    it('builds correct query string with all filters', async () => {
      const mockResponse = { count: 1, results: [{}] };
      vi.spyOn(apiClient, 'apiFetchRaw').mockResolvedValue(mockResponse as any);

      await getBusinessRulePolicies({
        step_type: 'aap',
        platform: 'linux',
        is_active: true,
        page: 2,
        page_size: 25,
      });

      const callArg = (apiClient.apiFetchRaw as ReturnType<typeof vi.spyOn>).mock.calls[0][0] as string;
      expect(callArg).toContain('step_type=aap');
      expect(callArg).toContain('platform=linux');
      expect(callArg).toContain('is_active=true');
      expect(callArg).toContain('page=2');
      expect(callArg).toContain('page_size=25');
    });
  });

  describe('getBusinessRulePolicy', () => {
    it('calls apiFetch with the correct id', async () => {
      const mockPolicy = { id: 7, name: 'rule-1' };
      vi.spyOn(apiClient, 'apiFetch').mockResolvedValue(mockPolicy as any);

      const result = await getBusinessRulePolicy(7);

      expect(apiClient.apiFetch).toHaveBeenCalledWith('/admin/business-rule-policies/7/');
      expect(result).toEqual(mockPolicy);
    });
  });

  describe('createBusinessRulePolicy', () => {
    it('sends POST /admin/business-rule-policies/ with body JSON', async () => {
      const payload = { name: 'new-rule', step_type: 'aap', platform: 'linux', is_active: true, rule_json: '{}' } as any;
      const mockResponse = { id: 10, ...payload };
      vi.spyOn(apiClient, 'apiFetch').mockResolvedValue(mockResponse as any);

      const result = await createBusinessRulePolicy(payload);

      expect(apiClient.apiFetch).toHaveBeenCalledWith('/admin/business-rule-policies/', {
        method: 'POST',
        body: JSON.stringify(payload),
      });
      expect(result).toEqual(mockResponse);
    });
  });

  describe('updateBusinessRulePolicy', () => {
    it('sends PATCH /admin/business-rule-policies/{id}/ with body JSON', async () => {
      const payload = { name: 'updated-rule' } as any;
      const mockResponse = { id: 10, name: 'updated-rule' };
      vi.spyOn(apiClient, 'apiFetch').mockResolvedValue(mockResponse as any);

      const result = await updateBusinessRulePolicy(10, payload);

      expect(apiClient.apiFetch).toHaveBeenCalledWith('/admin/business-rule-policies/10/', {
        method: 'PATCH',
        body: JSON.stringify(payload),
      });
      expect(result).toEqual(mockResponse);
    });
  });

  describe('deleteBusinessRulePolicy', () => {
    it('sends DELETE /admin/business-rule-policies/{id}/', async () => {
      vi.spyOn(apiClient, 'apiFetch').mockResolvedValue(undefined as any);

      await deleteBusinessRulePolicy(10);

      expect(apiClient.apiFetch).toHaveBeenCalledWith('/admin/business-rule-policies/10/', { method: 'DELETE' });
    });
  });
});

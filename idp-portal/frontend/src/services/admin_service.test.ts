/**
 * Admin service tests (Story 2.1, 2.4, 9.5, 18.1).
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import * as adminService from './admin_service';
import * as apiClient from './api_client';

vi.mock('./api_client', () => ({
  apiFetch: vi.fn(),
  apiFetchRaw: vi.fn(),
}));

describe('admin_service', () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  describe('createAction', () => {
    it('POSTs action to /admin/actions/', async () => {
      const mock = { id: 1, name: 'New Action' };
      vi.mocked(apiClient.apiFetch).mockResolvedValue(mock as any);

      const result = await adminService.createAction({
        name: 'New Action',
        engine: 'Oracle',
        parameters_schema: {},
      });

      expect(apiClient.apiFetch).toHaveBeenCalledWith('/admin/actions/', {
        method: 'POST',
        body: expect.any(String),
      });
      expect(result).toEqual(mock);
    });
  });

  describe('getAdminActions', () => {
    it('fetches without filters', async () => {
      vi.mocked(apiClient.apiFetchRaw).mockResolvedValue({ data: [], pagination: {} } as any);

      await adminService.getAdminActions();

      expect(apiClient.apiFetchRaw).toHaveBeenCalledWith('/admin/actions/');
    });

    it('appends filter params', async () => {
      vi.mocked(apiClient.apiFetchRaw).mockResolvedValue({ data: [], pagination: {} } as any);

      await adminService.getAdminActions({
        status: 'published',
        engine: 'Oracle',
        page: 2,
        page_size: 20,
        include_disabled: true,
      });

      const url = vi.mocked(apiClient.apiFetchRaw).mock.calls[0][0] as string;
      expect(url).toContain('status=published');
      expect(url).toContain('engine=Oracle');
      expect(url).toContain('page=2');
      expect(url).toContain('page_size=20');
      expect(url).toContain('include_disabled=true');
    });
  });

  describe('checkActionNameAvailable', () => {
    it('returns available when API says true', async () => {
      vi.mocked(apiClient.apiFetchRaw).mockResolvedValue({ available: true } as any);

      const result = await adminService.checkActionNameAvailable('MyAction');

      expect(result).toBe(true);
    });

    it('returns false when API says not available', async () => {
      vi.mocked(apiClient.apiFetchRaw).mockResolvedValue({ available: false } as any);

      const result = await adminService.checkActionNameAvailable('Taken');

      expect(result).toBe(false);
    });

    it('excludes action ID when editing', async () => {
      vi.mocked(apiClient.apiFetchRaw).mockResolvedValue({ available: true } as any);

      await adminService.checkActionNameAvailable('MyAction', 5);

      const url = vi.mocked(apiClient.apiFetchRaw).mock.calls[0][0] as string;
      expect(url).toContain('exclude_id=5');
    });
  });

  describe('getAction', () => {
    it('fetches action by ID', async () => {
      const mock = { id: 1, name: 'Test' };
      vi.mocked(apiClient.apiFetch).mockResolvedValue(mock as any);

      const result = await adminService.getAction(1);

      expect(apiClient.apiFetch).toHaveBeenCalledWith('/admin/actions/1/');
      expect(result).toEqual(mock);
    });
  });

  describe('updateAction', () => {
    it('PATCHes action', async () => {
      vi.mocked(apiClient.apiFetch).mockResolvedValue({} as any);

      await adminService.updateAction(1, { name: 'Updated', engine: 'Oracle', parameters_schema: {} });

      expect(apiClient.apiFetch).toHaveBeenCalledWith('/admin/actions/1/', {
        method: 'PATCH',
        body: expect.any(String),
      });
    });
  });

  describe('updateActionSteps', () => {
    it('PUTs execution steps', async () => {
      vi.mocked(apiClient.apiFetch).mockResolvedValue({} as any);

      await adminService.updateActionSteps(1, { steps: [] });

      expect(apiClient.apiFetch).toHaveBeenCalledWith('/admin/actions/1/execution-steps/', {
        method: 'PUT',
        body: expect.any(String),
      });
    });
  });

  describe('updateActionStatus', () => {
    it('PATCHes status transition', async () => {
      vi.mocked(apiClient.apiFetch).mockResolvedValue({} as any);

      await adminService.updateActionStatus(1, 'publish');

      expect(apiClient.apiFetch).toHaveBeenCalledWith('/admin/actions/1/status/', {
        method: 'PATCH',
        body: JSON.stringify({ transition: 'publish' }),
      });
    });
  });

  describe('getTags', () => {
    it('fetches tags', async () => {
      const mock = [{ id: 1, name: 'rac' }];
      vi.mocked(apiClient.apiFetch).mockResolvedValue(mock as any);

      const result = await adminService.getTags();

      expect(apiClient.apiFetch).toHaveBeenCalledWith('/tags/');
      expect(result).toEqual(mock);
    });
  });

  describe('updateActionTags', () => {
    it('PUTs tag_ids', async () => {
      vi.mocked(apiClient.apiFetch).mockResolvedValue({} as any);

      await adminService.updateActionTags(1, { tag_ids: [1, 2] });

      expect(apiClient.apiFetch).toHaveBeenCalledWith('/admin/actions/1/tags/', {
        method: 'PUT',
        body: JSON.stringify({ tag_ids: [1, 2] }),
      });
    });

    it('PUTs tag_names for create-on-the-fly', async () => {
      vi.mocked(apiClient.apiFetch).mockResolvedValue({} as any);

      await adminService.updateActionTags(1, { tag_names: ['new-tag'] });

      expect(apiClient.apiFetch).toHaveBeenCalledWith('/admin/actions/1/tags/', {
        method: 'PUT',
        body: JSON.stringify({ tag_names: ['new-tag'] }),
      });
    });
  });

  describe('fetchAdminAnalytics', () => {
    it('fetches analytics with default 90 days', async () => {
      vi.mocked(apiClient.apiFetch).mockResolvedValue({} as any);

      await adminService.fetchAdminAnalytics();

      expect(apiClient.apiFetch).toHaveBeenCalledWith('/admin/analytics/?days=90');
    });

    it('fetches analytics with custom days', async () => {
      vi.mocked(apiClient.apiFetch).mockResolvedValue({} as any);

      await adminService.fetchAdminAnalytics(30);

      expect(apiClient.apiFetch).toHaveBeenCalledWith('/admin/analytics/?days=30');
    });
  });

  describe('updateRemediationRules', () => {
    it('PUTs remediation rules', async () => {
      vi.mocked(apiClient.apiFetch).mockResolvedValue({} as any);

      await adminService.updateRemediationRules(1, []);

      expect(apiClient.apiFetch).toHaveBeenCalledWith('/admin/actions/1/remediation-rules/', {
        method: 'PUT',
        body: JSON.stringify({ remediation_rules: [] }),
      });
    });
  });

  describe('updateBusinessRulePolicies', () => {
    it('PUTs business rule policies', async () => {
      vi.mocked(apiClient.apiFetch).mockResolvedValue({} as any);

      await adminService.updateBusinessRulePolicies(1, { policies: [] } as any);

      expect(apiClient.apiFetch).toHaveBeenCalledWith('/admin/actions/1/business-rule-policies/', {
        method: 'PUT',
        body: JSON.stringify({ business_rule_policies: { policies: [] } }),
      });
    });
  });

  describe('patchAction', () => {
    it('PATCHes partial data', async () => {
      vi.mocked(apiClient.apiFetch).mockResolvedValue({} as any);

      await adminService.patchAction(1, { business_rule_policy_id: 5 });

      expect(apiClient.apiFetch).toHaveBeenCalledWith('/admin/actions/1/', {
        method: 'PATCH',
        body: JSON.stringify({ business_rule_policy_id: 5 }),
      });
    });
  });

  describe('deleteAction', () => {
    it('DELETEs action', async () => {
      vi.mocked(apiClient.apiFetch).mockResolvedValue(undefined as any);

      await adminService.deleteAction(1);

      expect(apiClient.apiFetch).toHaveBeenCalledWith('/admin/actions/1/', { method: 'DELETE' });
    });
  });

  describe('deactivateAction', () => {
    it('PUTs deactivate without confirmed', async () => {
      vi.mocked(apiClient.apiFetchRaw).mockResolvedValue({
        status: 'requires_confirmation',
        affected_workflows: [],
      } as any);

      const result = await adminService.deactivateAction(1, 'reason');

      expect(apiClient.apiFetchRaw).toHaveBeenCalledWith('/admin/actions/1/deactivate/', {
        method: 'PUT',
        body: JSON.stringify({ deletion_reason: 'reason' }),
      });
      expect((result as adminService.DeactivateConfirmation).status).toBe('requires_confirmation');
    });

    it('PUTs deactivate with confirmed=true', async () => {
      vi.mocked(apiClient.apiFetchRaw).mockResolvedValue({
        data: {},
        deactivated_workflows: [],
      } as any);

      await adminService.deactivateAction(1, 'reason', true);

      expect(apiClient.apiFetchRaw).toHaveBeenCalledWith(
        '/admin/actions/1/deactivate/?confirmed=true',
        expect.any(Object)
      );
    });
  });

  describe('reactivateAction', () => {
    it('PUTs reactivate', async () => {
      vi.mocked(apiClient.apiFetch).mockResolvedValue({} as any);

      await adminService.reactivateAction(1);

      expect(apiClient.apiFetch).toHaveBeenCalledWith('/admin/actions/1/reactivate/', {
        method: 'PUT',
      });
    });
  });

  describe('getEligibleActionsForWorkflow', () => {
    it('retourne une liste d\'actions publiées depuis l\'API', async () => {
      const mockActions = [
        { id: 1, name: 'Action A', engine: 'Oracle', status: 'published', created_at: '2025-01-01', execution_count: 5 },
        { id: 2, name: 'Action B', engine: 'SQL Server', status: 'published', created_at: '2025-01-02', execution_count: 3 },
      ];
      vi.mocked(apiClient.apiFetchRaw).mockResolvedValue({ data: mockActions } as any);

      const result = await adminService.getEligibleActionsForWorkflow();

      expect(apiClient.apiFetchRaw).toHaveBeenCalledWith('/admin/actions/eligible-for-workflow/');
      expect(result).toEqual(mockActions);
    });

    it('retourne [] si la réponse n\'a pas de champ data', async () => {
      vi.mocked(apiClient.apiFetchRaw).mockResolvedValue({} as any);

      const result = await adminService.getEligibleActionsForWorkflow();

      expect(result).toEqual([]);
    });

    it('uses results when data not present', async () => {
      const mockActions = [{ id: 1, name: 'A' }];
      vi.mocked(apiClient.apiFetchRaw).mockResolvedValue({ results: mockActions } as any);

      const result = await adminService.getEligibleActionsForWorkflow();

      expect(result).toEqual(mockActions);
    });

    it('lance une erreur quand l\'API retourne une erreur 500', async () => {
      vi.mocked(apiClient.apiFetchRaw).mockRejectedValue(new Error('Internal Server Error'));

      await expect(adminService.getEligibleActionsForWorkflow()).rejects.toThrow('Internal Server Error');
    });
  });

  describe('updateWorkflowSteps', () => {
    it('envoie les étapes au bon endpoint avec PUT', async () => {
      const mockDetail = {
        id: 10,
        name: 'Workflow Test',
        item_type: 'workflow',
        workflow_steps: [{ order: 1, name: 'Step 1', referenced_action_id: 1 }],
      };
      vi.mocked(apiClient.apiFetch).mockResolvedValue(mockDetail as any);

      const steps = [
        { order: 1, name: 'Step One', referenced_action_id: 1 },
        { order: 2, name: null, referenced_action_id: 2 },
      ];
      const result = await adminService.updateWorkflowSteps(10, { steps });

      expect(apiClient.apiFetch).toHaveBeenCalledWith('/admin/actions/10/execution-steps/', {
        method: 'PUT',
        body: JSON.stringify({ steps }),
      });
      expect(result).toEqual(mockDetail);
    });

    it('lance une erreur quand l\'API retourne 400 WORKFLOW_LOOP', async () => {
      vi.mocked(apiClient.apiFetch).mockRejectedValue(new Error('Circular dependency detected in workflow steps'));

      const steps = [{ order: 1, name: null, referenced_action_id: 5 }];
      await expect(adminService.updateWorkflowSteps(10, { steps })).rejects.toThrow(
        'Circular dependency detected in workflow steps'
      );
    });
  });
});

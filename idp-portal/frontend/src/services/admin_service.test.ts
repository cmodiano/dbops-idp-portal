/**
 * Admin service tests (Story 9.5, AC #2, #3).
 * - getEligibleActionsForWorkflow
 * - updateWorkflowSteps
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { getEligibleActionsForWorkflow, updateWorkflowSteps } from './admin_service';
import * as apiClient from './api_client';

describe('admin_service', () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  describe('getEligibleActionsForWorkflow', () => {
    it('retourne une liste d\'actions publiées depuis l\'API', async () => {
      const mockActions = [
        { id: 1, name: 'Action A', engine: 'Oracle', status: 'published', created_at: '2025-01-01', execution_count: 5 },
        { id: 2, name: 'Action B', engine: 'SQL Server', status: 'published', created_at: '2025-01-02', execution_count: 3 },
      ];
      vi.spyOn(apiClient, 'apiFetch').mockResolvedValue(mockActions as any);

      const result = await getEligibleActionsForWorkflow();

      expect(apiClient.apiFetch).toHaveBeenCalledWith('/admin/actions/eligible-for-workflow/');
      expect(result).toEqual(mockActions);
    });

    it('lance une erreur quand l\'API retourne une erreur 500', async () => {
      vi.spyOn(apiClient, 'apiFetch').mockRejectedValue(new Error('Internal Server Error'));

      await expect(getEligibleActionsForWorkflow()).rejects.toThrow('Internal Server Error');
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
      vi.spyOn(apiClient, 'apiFetch').mockResolvedValue(mockDetail as any);

      const steps = [
        { order: 1, name: 'Step One', referenced_action_id: 1 },
        { order: 2, name: null, referenced_action_id: 2 },
      ];
      const result = await updateWorkflowSteps(10, { steps });

      expect(apiClient.apiFetch).toHaveBeenCalledWith('/admin/actions/10/execution-steps/', {
        method: 'PUT',
        body: JSON.stringify({ steps }),
      });
      expect(result).toEqual(mockDetail);
    });

    it('lance une erreur quand l\'API retourne 400 WORKFLOW_LOOP', async () => {
      vi.spyOn(apiClient, 'apiFetch').mockRejectedValue(new Error('Circular dependency detected in workflow steps'));

      const steps = [{ order: 1, name: null, referenced_action_id: 5 }];
      await expect(updateWorkflowSteps(10, { steps })).rejects.toThrow(
        'Circular dependency detected in workflow steps'
      );
    });
  });
});

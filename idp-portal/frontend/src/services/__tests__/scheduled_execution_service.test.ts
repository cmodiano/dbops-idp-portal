/**
 * Tests for scheduled_execution_service (Story 11.5, 11.6, 11.7).
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import {
  createScheduledExecution,
  listScheduledExecutions,
  cancelScheduledExecution,
  toggleRecurringPattern,
} from '../scheduled_execution_service';
import * as apiClient from '../api_client';

// Mock the apiFetch and apiFetchRaw functions
vi.mock('../api_client', () => ({
  apiFetch: vi.fn(),
  apiFetchRaw: vi.fn(),
}));

describe('scheduled_execution_service', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('createScheduledExecution', () => {
    it('creates one-time scheduled execution', async () => {
      const mockResponse = {
        scheduled_execution_id: 42,
        action_id: 1,
        action_name: 'Test Action',
        environment: 'dev',
        status: 'pending',
        scheduled_at: '2026-03-15T14:30:00Z',
        created_at: '2026-02-02T10:00:00Z',
      };

      vi.mocked(apiClient.apiFetch).mockResolvedValue(mockResponse);

      const result = await createScheduledExecution({
        action_id: 1,
        environment: 'dev',
        parameters: {},
        scheduled_at: '2026-03-15T14:30:00Z',
      });

      expect(apiClient.apiFetch).toHaveBeenCalledWith('/scheduled-executions', {
        method: 'POST',
        body: JSON.stringify({
          action_id: 1,
          environment: 'dev',
          parameters: {},
          scheduled_at: '2026-03-15T14:30:00Z',
        }),
      });
      expect(result).toEqual(mockResponse);
    });

    it('creates daily recurring scheduled execution (Story 11.7)', async () => {
      const mockResponse = {
        scheduled_execution_id: 43,
        action_id: 1,
        action_name: 'Test Action',
        environment: 'prod',
        status: 'pending',
        scheduled_at: null,
        created_at: '2026-02-02T10:00:00Z',
        recurring_pattern: {
          pattern_type: 'daily',
          pattern_config: { hour: 2, minute: 30 },
          next_execution_date: '2026-02-03T02:30:00Z',
          is_active: true,
        },
      };

      vi.mocked(apiClient.apiFetch).mockResolvedValue(mockResponse);

      const result = await createScheduledExecution({
        action_id: 1,
        environment: 'prod',
        parameters: {},
        recurring_pattern: {
          pattern_type: 'daily',
          pattern_config: { hour: 2, minute: 30 },
        },
      });

      expect(apiClient.apiFetch).toHaveBeenCalledWith('/scheduled-executions', {
        method: 'POST',
        body: JSON.stringify({
          action_id: 1,
          environment: 'prod',
          parameters: {},
          recurring_pattern: {
            pattern_type: 'daily',
            pattern_config: { hour: 2, minute: 30 },
          },
        }),
      });
      expect(result.recurring_pattern?.pattern_type).toBe('daily');
      expect(result.recurring_pattern?.is_active).toBe(true);
    });

    it('creates weekly recurring scheduled execution (Story 11.7)', async () => {
      const mockResponse = {
        scheduled_execution_id: 44,
        action_id: 1,
        action_name: 'Weekly Backup',
        environment: 'staging',
        status: 'pending',
        scheduled_at: null,
        created_at: '2026-02-02T10:00:00Z',
        recurring_pattern: {
          pattern_type: 'weekly',
          pattern_config: { day_of_week: 5, hour: 22, minute: 0 },
          next_execution_date: '2026-02-07T22:00:00Z',
          is_active: true,
        },
      };

      vi.mocked(apiClient.apiFetch).mockResolvedValue(mockResponse);

      const result = await createScheduledExecution({
        action_id: 1,
        environment: 'staging',
        parameters: {},
        recurring_pattern: {
          pattern_type: 'weekly',
          pattern_config: { day_of_week: 5, hour: 22, minute: 0 },
        },
      });

      expect(result.recurring_pattern?.pattern_type).toBe('weekly');
      expect(result.recurring_pattern?.pattern_config.day_of_week).toBe(5);
    });
  });

  describe('listScheduledExecutions', () => {
    it('lists scheduled executions with default pagination (AC3: Story 26.9)', async () => {
      // AC3: Response uses flat format — apiFetchRaw returns full body
      const mockResponse = {
        data: [
          {
            scheduled_execution_id: 1,
            action_name: 'Test',
            status: 'pending',
            scheduled_at: '2026-03-15T14:30:00Z',
          },
        ],
        pagination: { page: 1, page_size: 50, total: 1, total_pages: 1 },
      };

      vi.mocked(apiClient.apiFetchRaw).mockResolvedValue(mockResponse);

      const result = await listScheduledExecutions();

      expect(apiClient.apiFetchRaw).toHaveBeenCalledWith(
        '/scheduled-executions?limit=50&offset=0'
      );
      expect(result.data).toHaveLength(1);
    });

    it('lists scheduled executions with filters', async () => {
      const mockResponse = {
        data: [],
        pagination: { page: 1, page_size: 50, total: 0, total_pages: 1 },
      };

      vi.mocked(apiClient.apiFetchRaw).mockResolvedValue(mockResponse);

      await listScheduledExecutions(
        { status: 'pending', action_id: 5 },
        20,
        10
      );

      expect(apiClient.apiFetchRaw).toHaveBeenCalledWith(
        '/scheduled-executions?status=pending&action_id=5&limit=20&offset=10'
      );
    });

    it('lists recurring executions with recurring_pattern in response (Story 11.7)', async () => {
      const mockResponse = {
        data: [
          {
            scheduled_execution_id: 1,
            action_name: 'Daily Backup',
            status: 'pending',
            scheduled_at: null,
            recurring_pattern: {
              pattern_type: 'daily',
              pattern_config: { hour: 2, minute: 30 },
              next_execution_date: '2026-02-03T02:30:00Z',
              is_active: true,
            },
          },
        ],
        pagination: { page: 1, page_size: 50, total: 1, total_pages: 1 },
      };

      vi.mocked(apiClient.apiFetchRaw).mockResolvedValue(mockResponse);

      const result = await listScheduledExecutions();

      expect(result.data[0].recurring_pattern).toBeDefined();
      expect(result.data[0].recurring_pattern?.pattern_type).toBe('daily');
      expect(result.data[0].scheduled_at).toBeNull();
    });
  });

  describe('cancelScheduledExecution', () => {
    it('cancels a pending scheduled execution', async () => {
      const mockResponse = {
        scheduled_execution_id: 1,
        status: 'cancelled',
      };

      vi.mocked(apiClient.apiFetch).mockResolvedValue(mockResponse);

      const result = await cancelScheduledExecution(1);

      expect(apiClient.apiFetch).toHaveBeenCalledWith(
        '/scheduled-executions/1',
        { method: 'PATCH', body: JSON.stringify({ status: 'cancelled' }) }
      );
      expect(result.status).toBe('cancelled');
    });
  });

  describe('toggleRecurringPattern (Story 11.7)', () => {
    it('disables a recurring pattern (AC9)', async () => {
      const mockResponse = {
        pattern_type: 'daily',
        pattern_config: { hour: 2, minute: 30 },
        next_execution_date: '2026-02-03T02:30:00Z',
        is_active: false,
      };

      vi.mocked(apiClient.apiFetch).mockResolvedValue(mockResponse);

      const result = await toggleRecurringPattern(1, false);

      expect(apiClient.apiFetch).toHaveBeenCalledWith(
        '/scheduled-executions/1/recurring-pattern',
        {
          method: 'PATCH',
          body: JSON.stringify({ is_active: false }),
        }
      );
      expect(result.is_active).toBe(false);
    });

    it('enables a recurring pattern (AC10)', async () => {
      const mockResponse = {
        pattern_type: 'weekly',
        pattern_config: { day_of_week: 1, hour: 8, minute: 0 },
        next_execution_date: '2026-02-10T08:00:00Z',
        is_active: true,
      };

      vi.mocked(apiClient.apiFetch).mockResolvedValue(mockResponse);

      const result = await toggleRecurringPattern(5, true);

      expect(apiClient.apiFetch).toHaveBeenCalledWith(
        '/scheduled-executions/5/recurring-pattern',
        {
          method: 'PATCH',
          body: JSON.stringify({ is_active: true }),
        }
      );
      expect(result.is_active).toBe(true);
    });
  });
});

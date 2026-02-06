/**
 * Scheduled Execution service (Story 11.5, 11.6, 11.7, 11.8).
 *
 * Provides functions to create, list, cancel scheduled executions,
 * toggle recurring patterns, and validate cron expressions.
 */

import { apiFetch } from './api_client';
import type {
  ScheduledExecutionCreateRequest,
  ScheduledExecutionResponse,
  ScheduledExecutionFilters,
  ScheduledExecutionListResponse,
  ScheduledExecutionCancelResponse,
  RecurringPatternResponse,
  CronValidationResponse,
  CronNextExecutionsResponse,
} from '../types/api';

/**
 * Create a scheduled execution (Story 11.5, AC3).
 *
 * @param request - Scheduled execution request (action_id, environment, parameters, scheduled_at)
 * @returns ScheduledExecutionResponse with scheduled_execution_id, status, scheduled_at
 * @throws Error with code:
 *   - INVALID_SCHEDULED_DATE (400): scheduled_at is in the past
 *   - PERMISSION_DENIED (403): user cannot execute this action in the environment
 *   - ACTION_NOT_FOUND (404): action not found or not published
 *   - INVALID_PARAMETERS (400): parameters validation failed
 */
export async function createScheduledExecution(
  request: ScheduledExecutionCreateRequest
): Promise<ScheduledExecutionResponse> {
  return apiFetch<ScheduledExecutionResponse>('/scheduled-executions', {
    method: 'POST',
    body: JSON.stringify(request),
  });
}

/**
 * List scheduled executions with filters (Story 11.6, AC1-AC3, AC7-AC9).
 *
 * RBAC:
 * - DBA: sees only their own scheduled executions
 * - DBOPS: sees all scheduled executions
 *
 * @param filters - Optional filters (status, action_id, scheduled_from, scheduled_to)
 * @param limit - Max results per page (default 50, max 100)
 * @param offset - Results offset for pagination
 * @returns ScheduledExecutionListItem[] with pagination info
 */
export async function listScheduledExecutions(
  filters: ScheduledExecutionFilters = {},
  limit: number = 50,
  offset: number = 0
): Promise<ScheduledExecutionListResponse> {
  const params = new URLSearchParams();

  if (filters.status) params.append('status', filters.status);
  if (filters.action_id) params.append('action_id', filters.action_id.toString());
  if (filters.scheduled_from) params.append('scheduled_from', filters.scheduled_from);
  if (filters.scheduled_to) params.append('scheduled_to', filters.scheduled_to);
  // Story 13.6: Extended filters for calendar view
  if (filters.environment) params.append('environment', filters.environment);
  if (filters.engine) params.append('engine', filters.engine);
  if (filters.platform) params.append('platform', filters.platform);
  params.append('limit', limit.toString());
  params.append('offset', offset.toString());

  const queryString = params.toString();
  const url = `/scheduled-executions${queryString ? `?${queryString}` : ''}`;

  return apiFetch<ScheduledExecutionListResponse>(url);
}

/**
 * Cancel a scheduled execution (Story 11.6, AC5).
 *
 * Only pending executions can be cancelled.
 *
 * RBAC:
 * - DBA: can cancel their own scheduled executions
 * - DBOPS: can cancel any scheduled execution
 *
 * @param scheduledExecutionId - ID of the scheduled execution to cancel
 * @returns Updated scheduled execution with status='cancelled'
 * @throws Error with code:
 *   - SCHEDULED_EXECUTION_NOT_FOUND (404): execution not found
 *   - INVALID_STATUS (400): execution not in 'pending' status
 *   - PERMISSION_DENIED (403): DBA trying to cancel another user's execution
 */
export async function cancelScheduledExecution(
  scheduledExecutionId: number
): Promise<ScheduledExecutionCancelResponse> {
  return apiFetch<ScheduledExecutionCancelResponse>(
    `/scheduled-executions/${scheduledExecutionId}`,
    {
      method: 'PATCH',
      body: JSON.stringify({ status: 'cancelled' }),
    }
  );
}

/**
 * Toggle recurring pattern is_active status (Story 11.7, AC9, AC10).
 *
 * Enables or disables a recurring pattern. When enabling, recalculates next_execution_date.
 *
 * RBAC:
 * - DBA: can toggle their own scheduled executions
 * - DBOPS: can toggle any scheduled execution
 *
 * @param scheduledExecutionId - ID of the scheduled execution
 * @param isActive - New active state for the recurring pattern
 * @returns Updated recurring pattern info
 * @throws Error with code:
 *   - SCHEDULED_EXECUTION_NOT_FOUND (404): execution not found
 *   - RECURRING_PATTERN_NOT_FOUND (404): execution is one-time (no recurring pattern)
 *   - PERMISSION_DENIED (403): DBA trying to toggle another user's pattern
 */
export async function toggleRecurringPattern(
  scheduledExecutionId: number,
  isActive: boolean
): Promise<RecurringPatternResponse> {
  return apiFetch<RecurringPatternResponse>(
    `/scheduled-executions/${scheduledExecutionId}/recurring-pattern`,
    {
      method: 'PATCH',
      body: JSON.stringify({ is_active: isActive }),
    }
  );
}

/**
 * Validate a cron expression (Story 11.8, AC2).
 *
 * Validates the cron expression syntax and semantics on the backend.
 *
 * @param expression - Cron expression to validate (5 fields: minute hour day month day_of_week)
 * @returns {valid: boolean, error: string} - validation result
 */
export async function validateCronExpression(
  expression: string
): Promise<CronValidationResponse> {
  const params = new URLSearchParams({ expression });
  return apiFetch<CronValidationResponse>(
    `/scheduled-executions/validate-cron?${params.toString()}`
  );
}

/**
 * Get next N execution dates for a cron expression (Story 11.8, AC2).
 *
 * Calculates the next N execution dates based on the cron expression.
 *
 * @param expression - Cron expression (5 fields)
 * @param count - Number of executions to return (1-10, default 5)
 * @returns Array of ISO 8601 datetime strings
 */
export async function getCronNextExecutions(
  expression: string,
  count: number = 5
): Promise<string[]> {
  const params = new URLSearchParams({
    expression,
    count: count.toString(),
  });
  const response = await apiFetch<CronNextExecutionsResponse>(
    `/scheduled-executions/cron-next-executions?${params.toString()}`
  );
  return response.executions;
}

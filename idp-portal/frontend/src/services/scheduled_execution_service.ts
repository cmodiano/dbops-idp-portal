/**
 * Scheduled Execution service (Story 11.5).
 *
 * Provides functions to create scheduled executions for later execution.
 */

import { apiFetch } from './api_client';
import type {
  ScheduledExecutionCreateRequest,
  ScheduledExecutionResponse,
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

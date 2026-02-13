import type { PaginationInfo } from './common';

// === Audit Types (Story 6.3) ===

/** Audit entry status filter (derived from action_type). */
export type AuditStatusFilter = 'success' | 'failed' | 'running';

/** Audit entry from GET /audit/executions (Story 6.3, AC1, AC3). */
export interface AuditExecutionEntry {
  id: number;
  timestamp: string;
  user_id: string;
  action_type: string;
  entity_type: string;
  entity_id: number; // execution_id
  action_name?: string; // Story 6.3, HIGH-4: enriched action name
  details: {
    action_id?: number;
    environment?: string;
    status?: string;
    parameters?: Record<string, unknown>;
    servicenow_change_id?: string;
    error_message?: string;
    [key: string]: unknown;
  } | null;
  ip_address: string | null;
  correlation_id: string | null;
  derived_status: 'success' | 'failed' | 'running' | 'unknown';
  /** Parent execution ID for workflow child grouping. */
  parent_execution_id?: number | null;
  /** Item type from action (action or workflow). */
  item_type?: string | null;
}

/** Filters for GET /audit/executions (Story 6.3, AC2, AC6). */
export interface AuditExecutionFilters {
  from?: string;
  to?: string;
  environment?: string;
  action_id?: number;
  user_id?: string;
  status?: AuditStatusFilter;
  sort?: string; // Sort field: timestamp, user_id, action_type
  order?: string; // Sort order: asc, desc
  limit?: number;
  offset?: number;
}

/** Response from GET /audit/executions (Story 6.3). */
export interface AuditExecutionListResponse {
  data: AuditExecutionEntry[];
  pagination: PaginationInfo;
}

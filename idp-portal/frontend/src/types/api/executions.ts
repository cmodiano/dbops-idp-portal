import type { ActionEngine, ActionPlatform, ItemType } from './catalog';

// === Execution Types (Story 4.1) ===

/** Execution environment (Story 4.1, AC2; Story 21.5: extended to string for dynamic inventory). */
export type ExecutionEnvironment = string;

/** Execution status (Story 4.1; Story 7.4: REJECTED; Story 18.6: INTEGRATION_ERROR). */
export type ExecutionStatusType = 'SUBMITTED' | 'INTEGRATION_ERROR' | 'PENDING_APPROVAL' | 'RUNNING' | 'COMPLETED' | 'FAILED' | 'CANCELLED' | 'REJECTED';

/** Execution scope for filtering (Story 8.9). */
export type ExecutionScope = 'all' | 'mine';

/** Request to create a new execution (Story 4.1, Task 1.1; Story 9.2 remediation; Story 13.2 targets). */
export interface ExecutionCreateRequest {
  action_id: number;
  /** Environment is optional when target_names is provided (backend derives it). */
  environment?: ExecutionEnvironment;
  /** Story 13.2, AC4: Target names for target-based execution. */
  target_names?: string[];
  parameters?: Record<string, unknown> | null;
  /** Story 4.12 (AC3): Per-workflow-step parameters keyed by step order (string). */
  workflow_step_parameters?: Record<string, { parameters: Record<string, unknown> }>;
  /** Story 9.2: Parent execution ID for remediation (optional). */
  parent_execution_id?: number | null;
  /** Story 31.8: Page me on failure (opt-in at execution time). */
  page_me?: boolean;
}

/** Response from POST /executions (Story 4.1, Task 1.1). */
export interface ExecutionCreateResponse {
  execution_id: number;
  status: ExecutionStatusType;
  created_at: string;
  /** Story 18.6: Error message when status is INTEGRATION_ERROR. */
  error_message?: string | null;
}

/** Execution target (Story 25.1, Story 58.2). */
export interface ExecutionTarget {
  target_type: string;
  target_id: string;
  target_name: string;
  target_metadata: Record<string, unknown> | null;
}

/** Execution record (Story 4.1; Story 7.4: approval fields; Story 9.2: remediation; Story 9.9: enrichment). */
export interface ExecutionResponse {
  id: number;
  action_id: number;
  action_name: string | null;
  user_id: number;
  /** Story 7.4: Display name of requester for pending approvals. */
  user_display_name?: string | null;
  environment: ExecutionEnvironment;
  parameters: Record<string, unknown> | null;
  status: ExecutionStatusType;
  servicenow_change_id: string | null;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
  /** Story 7.4: ID of DBA who approved/rejected. */
  approved_by?: number | null;
  /** Story 7.4: Timestamp of approval/rejection. */
  approved_at?: string | null;
  /** Story 7.4: Comment from approver. */
  approval_comment?: string | null;
  /** Story 9.2: Parent execution ID for remediation or workflow child. */
  parent_execution_id?: number | null;
  /** Parent's action item_type: 'workflow' = workflow child, else = remediation. */
  parent_item_type?: string | null;
  /** Story 18.6: Error message when status is INTEGRATION_ERROR. */
  error_message?: string | null;
  /** Story 9.9 AC6: Database engine from action (for Technologie column). */
  engine?: ActionEngine | null;
  /** Story 9.9 AC6: Execution platform from action. */
  platform?: ActionPlatform | null;
  /** Story 9.9 AC6: Item type (action or workflow) from action. */
  item_type?: ItemType;
  /** Story 9.9 AC6: Integration ID from execution config (for Plateforme column). */
  integration_id?: number | null;
  /** Story 9.9 AC6: Integration name from INTEGRATIONS. */
  integration_name?: string | null;
  /** Story 9.9 AC6: Integration icon URL from INTEGRATIONS. */
  integration_icon?: string | null;
  /** Story 25.1/58.2: Targets sélectionnés pour cette exécution. */
  targets?: ExecutionTarget[];
}

/** Execution step status (Story 4.6, Story 58.3: WAITING ajouté). */
export type ExecutionStepStatus = 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED' | 'SKIPPED' | 'WAITING';

/** Execution step type (Story 4.6). */
export type ExecutionStepTypeApi = 'vault' | 'servicenow' | 'platform' | 'prerequisite' | 'verification' | 'schedule_execution';

/** Execution step response from GET /executions/{id}/steps (Story 4.6). */
export interface ExecutionStepResponse {
  id: number;
  execution_id: number;
  step_order: number;
  step_name: string;
  /** step_id from workflow config — reliable matching (Story 65.6). */
  config_step_id?: string | null;
  step_type: ExecutionStepTypeApi;
  status: ExecutionStepStatus;
  started_at: string | null;
  completed_at: string | null;
  output: Record<string, unknown> | null;
  platform_job_id: string | null;
  error_message: string | null;
}

/** Step logs from GET /executions/{id}/steps/{step_id}/logs (Story 4.7, AC6). */
export interface StepLogsResponse {
  step_id: number;
  output: Record<string, unknown> | null;
  error_message: string | null;
  started_at: string | null;
  completed_at: string | null;
}

// === Dashboard Types (Story 5.1) ===

/** Dashboard statistics from GET /dashboard/stats (Story 5.1, AC1). */
export interface DashboardStats {
  executions_jour: number;
  taux_succes_pct: number;
  executions_en_cours: number;
  executions_en_erreur: number;
}

/** Filters for executions page (Story 9.10, AC3, AC4). */
export interface ExecutionFilters {
  /** Start date filter (YYYY-MM-DD). */
  start_date?: string | null;
  /** End date filter (YYYY-MM-DD). */
  end_date?: string | null;
  /** Filter by specific action ID. */
  action_id?: number | null;
  /** Filter by engine/technology. */
  engine?: string | null;
  /** Filter by tags (AND logic). */
  tags?: string[] | null;
  /** Filter by execution status. */
  status?: ExecutionStatusType | null;
  /** Filter by environment. */
  environment?: ExecutionEnvironment | null;
}

/** Recent execution for dashboard table (Story 5.1, AC2). */
export interface DashboardRecentExecution {
  id: number;
  action_name: string | null;
  user_display_name: string;
  environment: ExecutionEnvironment;
  status: ExecutionStatusType;
  created_at: string | null;
  /** Execution platform from action (e.g. AAP, GitHub Actions). */
  platform?: string | null;
  /** Engine/technology from action (e.g. Oracle, SQL Server, DB2). */
  engine?: string | null;
}

/** One day in the dashboard executions time series (line chart). */
export interface DashboardTimeSeriesPoint {
  date: string; // YYYY-MM-DD
  success: number;
  failed: number;
}

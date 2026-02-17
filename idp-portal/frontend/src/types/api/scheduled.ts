import type { ExecutionEnvironment } from './executions';

// === Scheduled Execution Types (Story 11.5, 11.7) ===

/** Status for scheduled executions (Story 11.5). */
export type ScheduledExecutionStatus = 'pending' | 'executed' | 'cancelled';

/** Recurring pattern type (Story 11.7, 11.8). */
export type RecurringPatternType = 'daily' | 'weekly' | 'cron';

/** Daily pattern configuration (Story 11.7, AC2). */
export interface DailyPatternConfig {
  hour: number; // 0-23
  minute: number; // 0-59
}

/** Weekly pattern configuration (Story 11.7, AC3). */
export interface WeeklyPatternConfig {
  day_of_week: number; // 1=Monday, 7=Sunday
  hour: number; // 0-23
  minute: number; // 0-59
}

/** Cron pattern configuration (Story 11.8, AC4). */
export interface CronPatternConfig {
  cron_expression: string; // 5 fields: minute hour day month day_of_week
}

/** Recurring pattern request (Story 11.7, 11.8). */
export interface RecurringPatternRequest {
  pattern_type: RecurringPatternType;
  pattern_config: DailyPatternConfig | WeeklyPatternConfig | CronPatternConfig;
}

/** Recurring pattern response (Story 11.7, 11.8). */
export interface RecurringPatternResponse {
  pattern_type: RecurringPatternType;
  pattern_config: DailyPatternConfig | WeeklyPatternConfig | CronPatternConfig;
  /** Next execution datetime in UTC (ISO 8601). */
  next_execution_date: string | null;
  /** Whether the recurrence is active. */
  is_active: boolean;
}

/** Request to create a scheduled execution (Story 11.5, 11.7; Story 13.2 targets). */
export interface ScheduledExecutionCreateRequest {
  action_id: number;
  environment: ExecutionEnvironment;
  parameters?: Record<string, unknown> | null;
  /** ISO 8601 datetime (UTC) for when to execute (mutually exclusive with recurring_pattern). */
  scheduled_at?: string | null;
  /** Recurring pattern configuration (Story 11.7, mutually exclusive with scheduled_at). */
  recurring_pattern?: RecurringPatternRequest | null;
  /** Story 13.2: Target names for target-based execution. */
  target_names?: string[];
}

/** Request to update a scheduled execution (Story 13.8, AC4). */
export interface ScheduledExecutionUpdateRequest {
  /** ISO 8601 datetime (UTC) for one-time executions. */
  scheduled_at?: string | null;
  /** Execution parameters (merged with existing; include _targets if targets changed). */
  parameters?: Record<string, unknown> | null;
  /** Environment (when not using targets). */
  environment?: ExecutionEnvironment;
  /** Target names (validated against RBAC; stored in parameters._targets). */
  target_names?: string[];
  /** Recurring pattern (for recurring executions). */
  recurring_pattern?: RecurringPatternRequest | null;
}

/** Response from POST /scheduled-executions (Story 11.5, 11.7). */
export interface ScheduledExecutionResponse {
  scheduled_execution_id: number;
  action_id: number;
  action_name: string;
  environment: ExecutionEnvironment;
  status: ScheduledExecutionStatus;
  /** ISO 8601 datetime (UTC, null for recurring). */
  scheduled_at: string | null;
  parameters: Record<string, unknown> | null;
  /** ISO 8601 datetime (UTC). */
  created_at: string;
  correlation_id: string;
  /** Recurring pattern info for recurring executions (Story 11.7). */
  recurring_pattern?: RecurringPatternResponse | null;
}

/** Filters for GET /scheduled-executions (Story 11.6, AC7-AC9; Story 13.6 extended filters). */
export interface ScheduledExecutionFilters {
  /** Filter by status (pending, executed, cancelled). */
  status?: ScheduledExecutionStatus;
  /** Filter by action ID. */
  action_id?: number;
  /** Filter by minimum scheduled_at date (ISO 8601). */
  scheduled_from?: string;
  /** Filter by maximum scheduled_at date (ISO 8601). */
  scheduled_to?: string;
  /** Story 13.6: Filter by environment (dev, staging, prod). */
  environment?: ExecutionEnvironment;
  /** Story 13.6: Filter by engine/technology. */
  engine?: string;
  /** Story 13.6: Filter by platform. */
  platform?: string;
}

/** List item for scheduled executions with enriched user info (Story 11.6, 11.7).
 * HIGH-1 FIX: Added correlation_id for AC10 (details modal requirement).
 * HIGH-2 FIX: Added execution_id for AC10 (link to effective execution when status=executed).
 * Story 11.7: Added recurring_pattern for recurring executions.
 */
export interface ScheduledExecutionListItem {
  scheduled_execution_id: number;
  action_id: number;
  action_name: string;
  user_id: number;
  user_name: string;
  environment: ExecutionEnvironment;
  /** ISO 8601 datetime (UTC, null for recurring). */
  scheduled_at: string | null;
  status: ScheduledExecutionStatus;
  /** ISO 8601 datetime (UTC). */
  created_at: string;
  parameters: Record<string, unknown> | null;
  /** HIGH-1 FIX: Correlation ID for request tracing (AC10). */
  correlation_id?: string | null;
  /** HIGH-2 FIX: ID of the effective execution if status=executed (AC10). */
  execution_id?: number | null;
  /** Story 11.7: Recurring pattern info for recurring executions. */
  recurring_pattern?: RecurringPatternResponse | null;
  /** Story 13.6 AC3: Technologie (engine) pour le popover détail. */
  engine?: string | null;
  /** Story 13.6 AC3: Plateforme d'exécution pour le popover détail. */
  platform?: string | null;
}

/** Response from GET /scheduled-executions (Story 11.6, AC3, AC8). */
export interface ScheduledExecutionListResponse {
  data: ScheduledExecutionListItem[];
  pagination: {
    page: number;
    page_size: number;
    total: number;
    total_pages: number;
  };
  /** AC8: All actions that have scheduled executions (for filter dropdown). */
  available_actions?: { action_id: number; action_name: string }[];
}

/** Response from PATCH /scheduled-executions/{id} (Story 11.6, AC5). */
export interface ScheduledExecutionCancelResponse {
  scheduled_execution_id: number;
  action_id: number;
  action_name: string;
  environment: ExecutionEnvironment;
  status: ScheduledExecutionStatus;
  scheduled_at: string;
  created_at: string;
}

/** Response from GET /scheduled-executions/validate-cron (Story 11.8, AC2). */
export interface CronValidationResponse {
  valid: boolean;
  error: string;
}

/** Response from GET /scheduled-executions/cron-next-executions (Story 11.8, AC2). */
export interface CronNextExecutionsResponse {
  executions: string[];
}

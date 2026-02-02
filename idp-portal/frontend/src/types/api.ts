export interface ApiResponse<T> {
  data: T;
}

export interface PaginatedResponse<T> {
  data: T[];
  pagination: {
    page: number;
    page_size: number;
    total: number;
    total_pages: number;
  };
}

export interface ApiError {
  error: {
    code: string;
    message: string;
    details?: Record<string, unknown>;
  };
}

// === Catalog Action Types (Story 2.1) ===
// Story 2.23: ActionCategory removed — use tags for categorization.

export type ActionEngine = 'Oracle' | 'SQL Server' | 'DB2';
export type ActionPlatform = 'AAP' | 'GitHub Actions' | 'Azure DevOps' | 'Terraform';
export type ActionStatus = 'draft' | 'published' | 'disabled';
/** Impact level for actions (Story 2.5, 2.18). */
export type ImpactLevel = 'low' | 'medium' | 'high' | 'critical';
/** Item type: action or workflow (Story 5.7, AC1). */
export type ItemType = 'action' | 'workflow';

export interface ActionCreate {
  name: string;
  description?: string | null;
  /** Story 5.7: item type (action or workflow). Default: action. */
  item_type?: ItemType;
  /** Engine is required for actions, optional for workflows (Story 5.7). */
  engine?: ActionEngine | null;
  /** Platform is required for actions, optional for workflows (Story 5.7). */
  platform?: ActionPlatform | null;
  parameters_schema?: Record<string, unknown> | null;
  /** Story 2.18: impact_rules includes criteria field. */
  impact_rules?: Record<string, { level: ImpactLevel; criteria?: string | null }> | null;
  /** Story 2.18 AC5: Default impact level when no rule matches the environment. */
  default_impact_level?: ImpactLevel | null;
  /** Story 2.24: change_model_code removed; change_type_config is in ExecutionStepsUpdate only. */
  /** Story 3.4 FR12: Markdown documentation for contextual help. */
  documentation_md?: string | null;
}

export interface ActionResponse {
  id: number;
  name: string;
  description: string | null;
  /** Story 5.7: item type (action or workflow). */
  item_type: ItemType;
  /** Engine (nullable for workflows). */
  engine: ActionEngine | null;
  /** Platform (nullable for workflows). */
  platform: ActionPlatform | null;
  parameters_schema: Record<string, unknown> | null;
  /** Story 2.18: impact_rules includes criteria field. */
  impact_rules: Record<string, { level: ImpactLevel; criteria?: string | null }> | null;
  /** Story 2.18 AC5: Default impact level when no rule matches the environment. */
  default_impact_level: ImpactLevel | null;
  /** Story 2.24: change_model_code removed from action level. */
  status: ActionStatus;
  created_by: number | null;
  created_at: string;
  updated_at: string | null;
  tags?: string[];
  /** Story 3.4 FR12: Markdown documentation for contextual help. */
  documentation_md?: string | null;
}

/** Per-environment change config (Story 2.24). required=true implies change_model_code required, alphanumeric max 50. */
export interface ChangeTypeConfigEntry {
  required: boolean;
  change_model_code?: string | null;
}

/** Workflow step - reference to an existing action (Story 5.7, AC2). */
export interface WorkflowStep {
  order: number;
  name: string | null;
  referenced_action_id: number;
}

/** Request to update workflow steps (Story 5.7, AC2). */
export interface WorkflowStepsUpdate {
  steps: WorkflowStep[];
}

export interface ActionDetail extends ActionResponse {
  /** Story 2.14: rbac_policies removed — RBAC now managed via profiles. */
  execution_steps: ExecutionStep[] | null;
  /** Story 5.7: workflow steps for workflows (action references). */
  workflow_steps: WorkflowStep[] | null;
  /** Story 2.24: per-env { required, change_model_code }. */
  change_type_config: Record<string, ChangeTypeConfigEntry> | null;
  /* documentation_md is inherited from ActionResponse (Story 3.4) */
  /** Story 9.1: Remediation rules for auto-suggesting corrective actions. */
  remediation_rules?: RemediationRule[] | null;
}

// === Execution Steps Types (Story 2.2; Story 2.7 connector_type) ===

export type ExecutionStepType = 'prerequisite' | 'execution' | 'verification';

/** Connector type for execution steps (Story 2.7). Aligned with backend ConnectorType. */
export type ConnectorType =
  | 'aap'
  | 'servicenow'
  | 'azuredevops'
  | 'jira'
  | 'github_actions'
  | 'terraform'
  | 'none';

export interface ExecutionStep {
  order: number;
  name: string;
  type: ExecutionStepType;
  connector_type: ConnectorType;
  connector_config?: Record<string, unknown> | null;
  conditional_environments: string[] | null;
}

export interface ExecutionStepsUpdate {
  steps: ExecutionStep[];
  /** Story 2.24: per-env { required, change_model_code }. */
  change_type_config: Record<string, ChangeTypeConfigEntry> | null;
}

// === Status Transition Types (Story 2.4) ===
// Note: Story 2.3 RBAC by action types (UserProfileType, EnvironmentPermission, RbacPolicies,
// RbacPoliciesUpdate) removed in Story 2.14 — RBAC now managed via profiles.

export type StatusTransition = 'publish' | 'disable' | 'enable';

export interface StatusUpdateRequest {
  transition: StatusTransition;
}

export interface ActionListItem {
  id: number;
  name: string;
  /** Story 5.7: item type for workflow icon display. */
  item_type?: ItemType;
  status: ActionStatus;
  /** Engine (nullable for workflows). */
  engine: ActionEngine | null;
  created_at: string;
  execution_count: number;
  tags?: string[];
}

export interface AdminActionsFilters {
  status?: ActionStatus;
  engine?: ActionEngine;
  /** Story 5.7: filter by item type (action or workflow). */
  item_type?: ItemType;
  page?: number;
  page_size?: number;
}

export interface PaginationInfo {
  page: number;
  page_size: number;
  total_count: number;
  total_pages: number;
}

export interface ActionListResponse {
  data: ActionListItem[];
  pagination: PaginationInfo | null;
}

// === Preview Types (Story 2.5) ===
// Note: ImpactLevel moved to top of file (before ActionCreate) for Story 2.18.

// === Impact Rules Editor (Story 2.18) ===

/** Single impact rule definition for the visual editor (AC1–AC6). */
export interface ImpactRuleDefinition {
  /** Optional stable id for React key; assigned when adding or loading. */
  id?: string;
  /** Environment name: DEV, STAGING, PROD, etc. */
  environment: string;
  /** Impact level for this environment. */
  level: ImpactLevel;
  /** Justification / criteria for this impact level. */
  criteria: string | null;
}

// === Parameters Editor (Story 2.17) ===

/** JSON Schema type / format for a single parameter. Aligns with backend validate_parameters_schema. */
export type ParameterSchemaType =
  | 'string'
  | 'number'
  | 'integer'
  | 'boolean'
  | 'date'
  | 'date-time'
  | 'select';

/** Single parameter definition for the visual editor (AC2). */
export interface ParameterDefinition {
  /** Optional stable id for React key / DnD; assigned when adding or loading. */
  id?: string;
  name: string;
  type: ParameterSchemaType;
  required: boolean;
  default?: string;
  description?: string;
  /** When type is 'select', list of enum options. */
  enum?: string[];
}

// === Profile Types (Story 2.9, FR25a) ===

export interface ProfileCreate {
  name: string;
  description?: string | null;
  ad_group: string;
  is_admin?: boolean;
  is_auditor?: boolean;
}

export interface ProfileUpdate {
  name?: string | null;
  description?: string | null;
  ad_group?: string | null;
  is_admin?: boolean | null;
  is_auditor?: boolean | null;
}

export interface ProfileResponse {
  id: number;
  name: string;
  description: string | null;
  ad_group: string;
  is_admin: boolean;
  is_auditor: boolean;
  created_at: string;
  updated_at: string;
}

export interface ProfileListItem {
  id: number;
  name: string;
  ad_group: string;
  permission_count: number;
  created_at: string;
}

/** Story 2.10: Actions/env permissions per profile (AC2–AC5). */
export type ProfileActionsType = 'list' | 'pattern' | 'all';

export interface ProfileActionPermissionsUpdate {
  actions_type: ProfileActionsType;
  action_ids?: number[] | null;
  tag_patterns?: string[] | null;
  environments?: string[] | null;
}

export interface ProfileActionPermissionsResponse {
  actions_type: ProfileActionsType;
  action_ids: number[];
  tag_patterns: string[];
  environments: string[];
}

/** Story 2.11: Target permissions per profile (AC1–AC5). */
export type ProfileTargetsType = 'list' | 'pattern' | 'all';

export interface ProfileTargetPermissionsUpdate {
  targets_type: ProfileTargetsType;
  target_names?: string[] | null;
  target_patterns?: string[] | null;
}

export interface ProfileTargetPermissionsResponse {
  targets_type: ProfileTargetsType;
  target_names: string[];
  target_patterns: string[];
}

// === Integration Types (Story 2.28, 4.9) ===

/** Story 4.9 AC1: Integration type is now free-form string (not enum).
 * Suggested types for UI autocomplete (legacy types, not enforced). */
export const SUGGESTED_INTEGRATION_TYPES = [
  'aap',
  'servicenow',
  'terraform',
  'azuredevops',
  'jira',
  'github_actions',
] as const;

/** Authentication flow types (Story 4.9 AC2). */
export type AuthFlow = 'token' | 'basic' | 'basic_then_token' | 'pat';

/** Labels for auth flows (french). */
export const AUTH_FLOW_LABELS: Record<AuthFlow, string> = {
  token: 'Token (Bearer)',
  basic: 'Basic (Username/Password)',
  basic_then_token: 'Basic puis Token',
  pat: 'PAT (Personal Access Token)',
};

export interface IntegrationCreate {
  type: string; // Story 4.9 AC1: free-form platform name (1-100 chars)
  name: string;
  base_url: string;
  credential_ref?: string | null;
  icon?: string | null;
  auth_flow?: AuthFlow | null; // Story 4.9 AC2: authentication flow
}

export interface IntegrationUpdate {
  type?: string; // Story 4.9 AC1: free-form platform name
  name?: string;
  base_url?: string;
  credential_ref?: string | null;
  icon?: string | null;
  auth_flow?: AuthFlow | null; // Story 4.9 AC2: authentication flow
}

export interface IntegrationResponse {
  id: number;
  type: string; // Story 4.9 AC1: free-form platform name
  name: string;
  base_url: string;
  credential_ref: string | null;
  icon: string | null;
  auth_flow: AuthFlow | null; // Story 4.9 AC2: authentication flow
  created_at: string;
  updated_at: string;
}

/** Alias for list display (same as full response). */
export type IntegrationListItem = IntegrationResponse;

/**
 * Subset of ActionDetail used for real-time preview in admin form.
 * Contains all fields needed to render ActionCard and ActionDrawerPreview.
 * Story 2.23: category removed — use tags for categorization.
 */
export interface ActionPreviewData {
  name: string;
  description: string | null;
  /** Story 5.7: item type for workflow icon display. */
  item_type?: ItemType;
  engine: ActionEngine | null;
  platform: ActionPlatform | null;
  impact_level: ImpactLevel | null;
  parameters_schema: Record<string, unknown> | null;
  tags?: string[];
  /** Nombre d'exécutions (affiché si disponible, Task 1.1). */
  execution_count?: number | null;
  /** Story 3.4 FR12: Markdown documentation for contextual help. */
  documentation_md?: string | null;
  /** Story 8.1: Performance stats for action scorecard (optional, loaded separately). */
  stats?: ActionStats | null;
}

/**
 * Action performance statistics (Story 8.1, AC1, AC4).
 * Aggregated metrics over the last 30 days.
 */
export interface ActionStats {
  /** Success rate percentage (COMPLETED / (COMPLETED + FAILED) * 100). Null if no finished executions. */
  success_rate: number | null;
  /** Average execution time in milliseconds for COMPLETED executions. Null if no completed executions. */
  avg_execution_time_ms: number | null;
  /** Total number of executions in the period. */
  total_executions: number;
  /** Number of FAILED executions (incidents). */
  incidents_count: number;
}

// === Execution Types (Story 4.1) ===

/** Execution environment (Story 4.1, AC2). */
export type ExecutionEnvironment = 'dev' | 'staging' | 'prod';

/** Execution status (Story 4.1; Story 7.4: REJECTED). */
export type ExecutionStatusType = 'SUBMITTED' | 'PENDING_APPROVAL' | 'RUNNING' | 'COMPLETED' | 'FAILED' | 'CANCELLED' | 'REJECTED';

/** Execution scope for filtering (Story 8.9). */
export type ExecutionScope = 'all' | 'mine';

/** Request to create a new execution (Story 4.1, Task 1.1; Story 9.2 remediation). */
export interface ExecutionCreateRequest {
  action_id: number;
  environment: ExecutionEnvironment;
  parameters?: Record<string, unknown> | null;
  /** Story 9.2: Parent execution ID for remediation (optional). */
  parent_execution_id?: number | null;
}

/** Response from POST /executions (Story 4.1, Task 1.1). */
export interface ExecutionCreateResponse {
  execution_id: number;
  status: ExecutionStatusType;
  created_at: string;
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
  /** Story 9.2: Parent execution ID for remediation actions. */
  parent_execution_id?: number | null;
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
}

/** Execution step status (Story 4.6). */
export type ExecutionStepStatus = 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED' | 'SKIPPED';

/** Execution step type (Story 4.6). */
export type ExecutionStepTypeApi = 'vault' | 'servicenow' | 'platform' | 'prerequisite' | 'verification';

/** Execution step response from GET /executions/{id}/steps (Story 4.6). */
export interface ExecutionStepResponse {
  id: number;
  execution_id: number;
  step_order: number;
  step_name: string;
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

// === Remediation Types (Story 9.1, FR36) ===

/** Risk level for remediation rules. */
export type RiskLevel = 'low' | 'medium' | 'high';

/** Remediation rule configuration (Story 9.1, AC4).
 * Defines when an action should be suggested as corrective for a failed execution. */
export interface RemediationRule {
  /** Python regex pattern to match against error_message in EXECUTION_STEPS. */
  error_pattern: string;
  /** ID of the corrective action in ACTIONS_CATALOG. */
  target_action_id: number;
  /** List of environments where this rule applies (e.g., ['dev', 'staging', 'prod']). */
  environments: string[];
  /** Reserved for Story 9.3 (auto-remediation). False for Story 9.1. */
  auto_trigger: boolean;
  /** Risk level of the corrective action (low, medium, high). */
  risk_level: RiskLevel;
}

/** Remediation suggestion returned by GET /executions/{id}/remediation (Story 9.1, AC5). */
export interface RemediationSuggestion {
  /** ID of the suggested corrective action. */
  action_id: number;
  /** Name of the corrective action for display. */
  action_name: string;
  /** Description of the corrective action (may be null). */
  action_description: string | null;
  /** The rule that matched (for debugging/transparency). */
  matching_rule: RemediationRule;
}

/** Single remediation action attempt (Story 9.2, AC2). */
export interface RemediationAction {
  /** ID of the child execution. */
  execution_id: number;
  /** Name of the corrective action executed. */
  action_name: string;
  /** Status of the remediation execution. */
  status: ExecutionStatusType;
  /** When the remediation was created. */
  created_at: string;
  /** When the remediation completed (null if still running). */
  completed_at: string | null;
}

/** Context about remediation attempts for a failed execution (Story 9.2, AC2, AC3). */
export interface RemediationContext {
  /** Whether any remediation has been attempted. */
  has_remediation: boolean;
  /** Whether any remediation attempt succeeded. */
  successful_remediation: boolean;
  /** List of all remediation actions attempted. */
  remediation_actions: RemediationAction[];
}

// === Inventory Types (Story 4.1, Task 2) ===

/** Inventory item for dropdowns (Story 4.1, Task 2.1). */
export interface InventoryItem {
  id: string;
  name: string;
  environment: string | null;
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

// === Admin Analytics Types (Story 8.2) ===

/** Executions count per engine (Story 8.2, AC1). */
export interface EngineExecutions {
  engine: string;
  count: number;
}

/** Executions count per user profile (Story 8.2, AC1). */
export interface ProfileExecutions {
  profile: string;
  count: number;
}

/** Weekly adoption trend point (Story 8.2, AC2). */
export interface WeeklyTrendPoint {
  week_start: string; // YYYY-MM-DD
  engine: string;
  count: number;
}

/** Admin analytics dashboard data (Story 8.2, AC1, AC4). */
export interface AdminAnalytics {
  total_published_actions: number;
  executions_by_engine: EngineExecutions[];
  executions_by_profile: ProfileExecutions[];
  adoption_trend: WeeklyTrendPoint[];
}

// === Reporting Dashboard Types (Story 8.3) ===

/** Executions aggregated by database engine (Story 8.3, AC3, AC7). */
export interface TechnologyStats {
  /** Database engine name (e.g., Oracle, PostgreSQL, N/A). */
  engine: string;
  /** Total execution count for this engine. */
  count: number;
  /** Success rate percentage (0-100), null if no finished executions. */
  success_rate: number | null;
}

/** Executions aggregated by environment (Story 8.3, AC4, AC7). */
export interface EnvironmentStats {
  /** Environment name (dev, staging, prod). */
  environment: string;
  /** Total execution count for this environment. */
  count: number;
  /** Success rate percentage (0-100), null if no finished executions. */
  success_rate: number | null;
}

// === Dashboard Advanced Filters Types (Story 8.4) ===

/** Status values for execution filter (Story 8.4, Task 8.2).
 * Includes all execution statuses including approval workflow statuses (Story 7.4). */
export type DashboardFilterStatus = 'PENDING' | 'SUBMITTED' | 'RUNNING' | 'COMPLETED' | 'FAILED' | 'CANCELLED' | 'PENDING_APPROVAL' | 'REJECTED';

/** Advanced filters for dashboard endpoints (Story 8.4, AC1, AC6, AC7). */
export interface DashboardFilters {
  /** Filter by database engine (e.g., 'aap', 'terraform'). */
  engine?: string;
  /** Filter by environment (e.g., 'dev', 'staging', 'prod'). */
  environment?: string;
  /** Filter by action tags (actions having any of these tags). */
  tags?: string[];
  /** Filter by execution status. */
  status?: DashboardFilterStatus;
  /** Custom period start (YYYY-MM-DD). */
  fromDate?: string;
  /** Custom period end (YYYY-MM-DD). */
  toDate?: string;
  /** Period in days (used when fromDate/toDate not provided). */
  days?: number;
}

/** Available filter options from API (Story 8.4, Task 14). */
export interface FilterOptions {
  /** Available database engines from published actions. */
  engines: string[];
  /** Used environments from executions. */
  environments: string[];
  /** All available tags. */
  tags: string[];
  /** All possible execution statuses. */
  statuses: string[];
}

// === Dashboard Export Types (Story 8.5) ===

/** Export format for dashboard reports (Story 8.5, AC1). */
export type ExportFormat = 'csv' | 'pdf';

// === Dashboard Comparison Types (Story 8.6) ===

/** Dimension for comparison analysis (Story 8.6, AC1, AC7). */
export type ComparisonDimension = 'technology' | 'environment' | 'period';

/** Metrics available for comparison (Story 8.6, AC2, AC7). */
export type ComparisonMetric = 'success_rate' | 'avg_time' | 'execution_count' | 'incident_count';

/** Statistics for one side of a comparison (Story 8.6, AC7). */
export interface ComparisonStats {
  /** Success rate percentage (0-100), null if no finished executions. */
  success_rate: number | null;
  /** Average execution time in seconds, null if no completed executions. */
  avg_time: number | null;
  /** Total execution count. */
  execution_count: number;
  /** Count of failed executions (incidents). */
  incident_count: number;
}

/** Result of a comparison between two values (Story 8.6, AC7). */
export interface ComparisonResult {
  /** Dimension being compared (technology, environment, period). */
  dimension: ComparisonDimension;
  /** First value being compared (label). */
  value1: string;
  /** Second value being compared (label). */
  value2: string;
  /** Statistics for the first value. */
  value1_stats: ComparisonStats;
  /** Statistics for the second value. */
  value2_stats: ComparisonStats;
  /** Percentage change for each metric ((value2 - value1) / value1 * 100). */
  deltas: Record<ComparisonMetric | string, number | null>;
}

/** Filters for comparison request (Story 8.6, AC1-AC4, AC7). */
export interface ComparisonFilters {
  /** Dimension to compare (technology, environment, period). */
  dimension: ComparisonDimension;
  /** First value to compare. */
  value1: string;
  /** Second value to compare. */
  value2: string;
  /** Metrics to include (all if not specified). */
  metrics?: ComparisonMetric[];
  /** Period in days (for technology/environment dimensions). */
  days?: number;
  /** Start date of first period (for period dimension). */
  period1Start?: string;
  /** End date of first period (for period dimension). */
  period1End?: string;
  /** Start date of second period (for period dimension). */
  period2Start?: string;
  /** End date of second period (for period dimension). */
  period2End?: string;
}

// === Scheduled Execution Types (Story 11.5) ===

/** Status for scheduled executions (Story 11.5). */
export type ScheduledExecutionStatus = 'pending' | 'executed' | 'cancelled';

/** Request to create a scheduled execution (Story 11.5, AC3). */
export interface ScheduledExecutionCreateRequest {
  action_id: number;
  environment: ExecutionEnvironment;
  parameters?: Record<string, unknown> | null;
  /** ISO 8601 datetime (UTC) for when to execute. */
  scheduled_at: string;
}

/** Response from POST /scheduled-executions (Story 11.5, AC3). */
export interface ScheduledExecutionResponse {
  scheduled_execution_id: number;
  action_id: number;
  action_name: string;
  environment: ExecutionEnvironment;
  status: ScheduledExecutionStatus;
  /** ISO 8601 datetime (UTC). */
  scheduled_at: string;
  parameters: Record<string, unknown> | null;
  /** ISO 8601 datetime (UTC). */
  created_at: string;
  correlation_id: string;
}

/** Filters for GET /scheduled-executions (Story 11.6, AC7-AC9). */
export interface ScheduledExecutionFilters {
  /** Filter by status (pending, executed, cancelled). */
  status?: ScheduledExecutionStatus;
  /** Filter by action ID. */
  action_id?: number;
  /** Filter by minimum scheduled_at date (ISO 8601). */
  scheduled_from?: string;
  /** Filter by maximum scheduled_at date (ISO 8601). */
  scheduled_to?: string;
}

/** List item for scheduled executions with enriched user info (Story 11.6, AC3, AC10).
 * HIGH-1 FIX: Added correlation_id for AC10 (details modal requirement).
 * HIGH-2 FIX: Added execution_id for AC10 (link to effective execution when status=executed).
 */
export interface ScheduledExecutionListItem {
  scheduled_execution_id: number;
  action_id: number;
  action_name: string;
  user_id: number;
  user_name: string;
  environment: ExecutionEnvironment;
  /** ISO 8601 datetime (UTC). */
  scheduled_at: string;
  status: ScheduledExecutionStatus;
  /** ISO 8601 datetime (UTC). */
  created_at: string;
  parameters: Record<string, unknown> | null;
  /** HIGH-1 FIX: Correlation ID for request tracing (AC10). */
  correlation_id?: string | null;
  /** HIGH-2 FIX: ID of the effective execution if status=executed (AC10). */
  execution_id?: number | null;
}

/** Response from GET /scheduled-executions (Story 11.6, AC3). */
export interface ScheduledExecutionListResponse {
  data: ScheduledExecutionListItem[];
  pagination: {
    page: number;
    page_size: number;
    total_count: number;
    total_pages: number;
  };
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

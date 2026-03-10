import type { PaginationInfo } from './common';
import type { RemediationRule } from './remediation';

// === Catalog Action Types (Story 2.1) ===
// Story 2.30: RefCategory type for administrable categories.
export interface RefCategory {
  id: number;
  code: string;
  label: string;
  display_order: number;
  is_active: number;
}

// Story 13.7: These types are now dynamic (loaded from REF_ENGINES and REF_PLATFORMS tables).
// The union types below are kept for backward compatibility, but values come from API.
// Consider using `string` instead for new code.
export type ActionEngine = 'Oracle' | 'SQL Server' | 'DB2' | string;
export type ActionPlatform = 'AAP' | 'Tower' | 'GitHub Actions' | 'Azure DevOps' | 'Terraform' | string;
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
  /** Story 2.30: Category code (optional, validated against REF_CATEGORIES). */
  category?: string | null;
  /** Engine is required for actions, optional for workflows (Story 5.7). */
  engine?: ActionEngine | null;
  /** Platform is required for actions, optional for workflows (Story 5.7). */
  platform?: ActionPlatform | null;
  /** Story 31.1: Integration FK (optional, derived from integration selection). */
  integration_id?: number | null;
  parameters_schema?: Record<string, unknown> | null;
  /** Story 2.18: impact_rules includes criteria field. */
  impact_rules?: Record<string, { level: ImpactLevel; criteria?: string | null }> | null;
  /** Story 2.18 AC5: Default impact level when no rule matches the environment. */
  default_impact_level?: ImpactLevel | null;
  /** Story 3.4 FR12: Markdown documentation for contextual help. */
  documentation_md?: string | null;
  /** Story 31.8: Notification channels configuration. */
  notification_config?: NotificationConfig | null;
  /** Story 28.4: FK to predefined business rule policy. */
  business_rule_policy_id?: number | null;
  /** Story 63.9: FK vers OutputSchema déclaré par l'admin pour cette action. */
  output_schema_id?: number | null;
}

export interface ActionResponse {
  id: number;
  name: string;
  description: string | null;
  /** Story 5.7: item type (action or workflow). */
  item_type: ItemType;
  /** Story 2.30: Category code (nullable). */
  category?: string | null;
  /** Engine (nullable for workflows). */
  engine: ActionEngine | null;
  /** Platform (nullable for workflows). */
  platform: ActionPlatform | null;
  /** Story 31.1: Integration FK (nullable). */
  integration_id?: number | null;
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
  /**
   * Story 13.2, AC3: Whether action requires target selection (default true).
   * Story 22.18: MED-6 fix (code-quality-assessment-2026-02-08.md:442-445).
   * Optional because frontend uses defensive logic (!== false) to assume true by default,
   * consistent with backend models.BooleanField(default=True).
   */
  requires_target?: boolean;
  /** Story 64.13: IaC drift tracking. */
  last_synced_at?: string | null;
  last_synced_hash?: string | null;
}

/** Story 31.8: Notification channel configuration. */
export interface NotificationChannel {
  type: 'email' | 'teams' | 'page_oncall';
  enabled: boolean;
  conditions: ('on_failure' | 'on_success' | 'always' | 'on_approval_required')[];
  /** Email only: "requester" or direct email address. */
  recipient?: string;
  /** Teams only: webhook URL or Vault reference. */
  webhook_url_ref?: string;
  /** Page on-call only: API URL (optional, falls back to settings). */
  api_url?: string;
}

/** Story 31.8: Notification configuration for actions. */
export interface NotificationConfig {
  channels: NotificationChannel[];
  page_individual_enabled: boolean;
}

// ADR-007 Story 57.13 — Step types for step-based workflows
// Story 57.16: Schedule step types
/** Source for scheduling date in a schedule_execution step. */
export type ScheduleSource = 'parameter' | 'fixed_offset' | 'recurring';

/** Configuration for a schedule_execution workflow step. */
export interface ScheduleStepConfig {
  /** Source de la date de planification. */
  schedule_source: ScheduleSource;
  /** Nom du paramètre contenant la date ISO 8601 (quand source='parameter'). */
  schedule_parameter_name?: string;
  /** Offset relatif à now() (quand source='fixed_offset'). Format: +Nd, +Nh, +Nw, +Nm. */
  fixed_offset?: string;
  /** Pattern récurrent (quand source='recurring'). */
  recurring_pattern?: {
    pattern_type: 'daily' | 'weekly' | 'cron';
    pattern_config: Record<string, unknown>;
  };
  /** Si true, hérite les paramètres de l'exécution courante (défaut: false). */
  inherit_parameters?: boolean;
  /** Si true, hérite les targets de l'exécution courante (défaut: false). */
  inherit_targets?: boolean;
  /** Mapping de paramètres additionnels. Clé = nom du param cible, Valeur = JSONPath ou valeur statique. */
  parameter_mapping?: Record<string, string>;
}

/** @deprecated parallel_group: supprimé du builder (Story 67-5), conservé pour rétro-compat exécutions. Sera supprimé en Story 67.7. */
export type WorkflowStepType = 'platform' | 'service_call' | 'http_request' | 'evaluation' | 'gate' | 'schedule_execution' | 'parallel_group';

/** Workflow step - reference to an existing action or special step type (Story 5.7, AC2; Story 16.2 branches & retry; Story 57.13 step types). */
export interface WorkflowStep {
  order: number;
  name: string | null;
  /** Story 57.13: Step type. Defaults to 'platform' for backward compatibility. */
  step_type?: WorkflowStepType;
  /** Story 18.3: Real action name from backend (resolved from referenced_action). */
  action_name?: string | null;
  /** Story 16.2: Stable ID for referencing in branches (optional for backward compatibility). */
  step_id?: string | null;
  /** Story 67.4: Multiple next step IDs on success (fan-out). */
  on_success_step_ids?: string[] | null;
  /** Story 67.4: Multiple next step IDs on error (fan-out). */
  on_error_step_ids?: string[] | null;
  /** Story 67.4: Join policy for convergence steps. */
  join_policy?: 'all_success' | 'one_success' | 'all_done' | 'all_failed' | 'one_failed' | null;
  // === platform ===
  /** Story 57.13: Optional for backward compat — required if step_type='platform'. */
  referenced_action_id?: number | null;
  /** Story 16.2: Enable retry for this step (platform only). */
  retry_enabled?: boolean;
  /** Story 16.2: Max retry attempts (default: 3). */
  retry_max_attempts?: number | null;
  /** Story 16.2: Retry interval in seconds (default: 60). */
  retry_interval_seconds?: number | null;
  /** Story 16.2: Backoff multiplier for exponential backoff (default: 2.0). */
  retry_backoff_multiplier?: number | null;
  // === service_call ===
  /** Story 57.13: Integration type for service_call steps ('servicenow' | 'vault' | 'jira'). */
  integration_type?: string | null;
  /** Story 57.13: Operation for service_call steps. */
  operation?: string | null;
  // === evaluation ===
  /** Story 57.13: Business rule policy ID for evaluation steps. */
  policy_id?: number | null;
  // === gate ===
  /** Story 57.13: Gate type for gate steps. */
  gate_type?: 'maintenance_window' | 'approval' | null;
  /** Story 57.13: Action on timeout for gate steps. */
  on_timeout?: 'FAIL' | 'SKIP' | null;
  /** Story 57.13: Step IDs to show to approver (gate type=approval only). */
  context_from?: string[] | null;
  /** Story 58.4: Profile IDs allowed to approve (gate type=approval only). Empty/null = all is_approver profiles eligible. */
  approver_profile_ids?: number[] | null;
  /** Story 57.13: Timeout duration string e.g. '24h', '30m'. */
  timeout?: string | null;
  // === http_request ===
  /** Story 57.13: URL for http_request steps. */
  url?: string | null;
  /** Story 57.13: HTTP method for http_request steps. */
  method?: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE' | null;
  /** Story 57.13: HTTP headers for http_request steps. */
  headers?: Record<string, string> | null;
  /** Story 57.13: Request timeout in seconds for http_request steps. */
  request_timeout?: number | null;
  // === schedule_execution ===
  /** Story 57.16: Configuration pour les steps de planification. */
  schedule_config?: ScheduleStepConfig | null;
  // === parallel_group — TODO Story 67.7: supprimer ces champs après migration ===
  /** Story 65.4: Liste des step_id à exécuter en parallèle (≥2 requis). */
  parallel_steps?: string[] | null;
  /** Story 65.4: Step suivant si tous les sous-steps réussissent. */
  on_all_success_step_id?: string | null;
  /** Story 65.4: Step suivant si au moins un sous-step échoue (fail-fast). */
  on_any_error_step_id?: string | null;
  // === shared (service_call, evaluation, http_request) ===
  /** Story 57.13: Condition for environment filtering. */
  condition?: { environment_in?: string[] } | null;
  /** Story 57.13: Input mapping (key → value expression). */
  input_mapping?: Record<string, unknown> | null;
  /** Story 57.13: Output mapping (key → JSONPath expression). */
  output_mapping?: Record<string, string> | null;
}

/** Request to update workflow steps (Story 5.7, AC2). */
export interface WorkflowStepsUpdate {
  steps: WorkflowStep[];
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
}

/** Story 28.1: Business rule policy criteria for review_if_modified. */
export interface BusinessRuleCriteria {
  resource_type?: string;
  attribute_paths?: string[];
}

/** Story 28.1: Business rule policy definition. */
export interface BusinessRulePolicy {
  when: {
    step_type: string;
    output_key?: string;
  };
  policy: {
    type: string;
    require_review_if_modified?: BusinessRuleCriteria[];
    auto_approve_if_none_match?: boolean;
  };
}

/** Story 28.1: Business rule policies JSON structure. */
export interface BusinessRulePoliciesData {
  on_step_output: BusinessRulePolicy[];
}

export interface ActionDetail extends ActionResponse {
  /** Story 2.14: rbac_policies removed — RBAC now managed via profiles. */
  execution_steps: ExecutionStep[] | null;
  /** Story 5.7: workflow steps for workflows (action references). */
  workflow_steps: WorkflowStep[] | null;
  /** Story 31.8: Notification channels configuration. */
  notification_config?: NotificationConfig | null;
  /* documentation_md is inherited from ActionResponse (Story 3.4) */
  /** Story 9.1: Remediation rules for auto-suggesting corrective actions. */
  remediation_rules?: RemediationRule[] | null;
  /** Story 28.1: Business rule policies evaluated on step output (inline legacy). */
  business_rule_policies?: BusinessRulePoliciesData | null;
  /** Story 28.4: FK to predefined business rule policy. */
  business_rule_policy_id?: number | null;
  /** Story 28.4: Name of the predefined business rule policy (computed). */
  business_rule_policy_name?: string | null;
  /** Story 63.9: FK vers OutputSchema déclaré par l'admin pour cette action. */
  output_schema_id?: number | null;
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
  /** Story 2.30: Category code (nullable). */
  category?: string | null;
  status: ActionStatus;
  /** Engine (nullable for workflows). */
  engine: ActionEngine | null;
  /** Story 57.13: Platform for grouping in ActionPalette (returned by eligible-for-workflow via ActionSerializer). */
  platform?: string | null;
  created_at: string;
  execution_count: number;
  tags?: string[];
  /** Story 18.1: soft-delete fields (present when include_disabled=true). */
  deleted_at?: string | null;
  deleted_by?: number | null;
  deletion_reason?: string | null;
  /** Story 22.18: MED-6 fix — Whether action requires target selection (default true). */
  requires_target?: boolean;
  /** Story 64.13: IaC drift tracking. */
  last_synced_at?: string | null;
  last_synced_hash?: string | null;
  updated_at?: string | null;
  /** Story 63.9: FK vers OutputSchema déclaré par l'admin pour cette action (lecture seule). */
  output_schema_id?: number | null;
}

// Story 57.13: BusinessRulePolicyListItem is defined in business_rules.ts (already exists)

export interface AdminActionsFilters {
  status?: ActionStatus;
  engine?: ActionEngine;
  /** Story 5.7: filter by item type (action or workflow). */
  item_type?: ItemType;
  page?: number;
  page_size?: number;
  /** Story 18.1 (AC4/AC5): include disabled actions. Default false. */
  include_disabled?: boolean;
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

/** Inventory source type for parameter fields (Story 23.5). */
export type InventorySourceType = 'servers' | 'instances' | 'databases';

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
  /** Story 23.5: Parameter value source — manual input or inventory selection. */
  source?: 'manual' | 'inventory';
  /** Story 23.5: Inventory entity type when source is 'inventory'. */
  inventory_type?: InventorySourceType;
  /** Story 37.5: Column used as value/label in inventory dropdown (optional). */
  inventory_value_column?: string;
}

/**
 * Subset of ActionDetail used for real-time preview in admin form.
 * Contains all fields needed to render ActionCard and ActionDrawerPreview.
 * Story 2.23: category removed — use tags for categorization.
 */
/** Story 69.2: Included action summary for workflow cards. */
export interface IncludedAction {
  id: number;
  name: string;
  engine: ActionEngine | null;
  parameters_schema?: Record<string, unknown> | null;
}

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
  /** Story 22.18: MED-6 fix — Whether action requires target selection (default true). */
  requires_target?: boolean;
  /** Story 69.2: List of technology engine codes for workflow cards. */
  technologies?: string[];
  /** Story 69.2: Included actions summary for workflow cards (prep for 69.3/69.4). */
  included_actions?: IncludedAction[];
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

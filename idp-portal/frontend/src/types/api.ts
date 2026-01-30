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

export interface ActionCreate {
  name: string;
  description?: string | null;
  engine: ActionEngine;
  platform: ActionPlatform;
  parameters_schema?: Record<string, unknown> | null;
  /** Story 2.18: impact_rules includes criteria field. */
  impact_rules?: Record<string, { level: ImpactLevel; criteria?: string | null }> | null;
  /** Story 2.18 AC5: Default impact level when no rule matches the environment. */
  default_impact_level?: ImpactLevel | null;
  /** Story 2.24: change_model_code removed; change_type_config is in ExecutionStepsUpdate only. */
}

export interface ActionResponse {
  id: number;
  name: string;
  description: string | null;
  engine: ActionEngine;
  platform: ActionPlatform;
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
}

/** Per-environment change config (Story 2.24). required=true implies change_model_code required, alphanumeric max 50. */
export interface ChangeTypeConfigEntry {
  required: boolean;
  change_model_code?: string | null;
}

export interface ActionDetail extends ActionResponse {
  /** Story 2.14: rbac_policies removed — RBAC now managed via profiles. */
  execution_steps: ExecutionStep[] | null;
  /** Story 2.24: per-env { required, change_model_code }. */
  change_type_config: Record<string, ChangeTypeConfigEntry> | null;
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
  status: ActionStatus;
  engine: ActionEngine;
  created_at: string;
  execution_count: number;
  tags?: string[];
}

export interface AdminActionsFilters {
  status?: ActionStatus;
  engine?: ActionEngine;
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

// === Integration Types (Story 2.28) ===

/** Integration platform type (aligned with backend IntegrationType). */
export type IntegrationType =
  | 'aap'
  | 'servicenow'
  | 'terraform'
  | 'azuredevops'
  | 'jira'
  | 'github_actions';

/** Labels for integration types (french). */
export const INTEGRATION_TYPE_LABELS: Record<IntegrationType, string> = {
  aap: 'AAP',
  servicenow: 'ServiceNow',
  terraform: 'Terraform',
  azuredevops: 'Azure DevOps',
  jira: 'Jira',
  github_actions: 'GitHub Actions',
};

/** Icon components for integration types (shared between Table and Form). */
export const INTEGRATION_TYPE_ICON_COLORS: Record<IntegrationType, string> = {
  aap: '#1890ff',
  servicenow: '#52c41a',
  terraform: '#722ed1',
  azuredevops: '#0078d4',
  jira: '#0052cc',
  github_actions: '#24292e',
};

/** Tag colors for integration types in table display. */
export const INTEGRATION_TYPE_TAG_COLORS: Record<IntegrationType, string> = {
  aap: 'blue',
  servicenow: 'green',
  terraform: 'purple',
  azuredevops: 'geekblue',
  jira: 'blue',
  github_actions: 'default',
};

export interface IntegrationCreate {
  type: IntegrationType;
  name: string;
  base_url: string;
  credential_ref?: string | null;
  icon?: string | null;
}

export interface IntegrationUpdate {
  type?: IntegrationType;
  name?: string;
  base_url?: string;
  credential_ref?: string | null;
  icon?: string | null;
}

export interface IntegrationResponse {
  id: number;
  type: IntegrationType;
  name: string;
  base_url: string;
  credential_ref: string | null;
  icon: string | null;
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
  engine: ActionEngine | null;
  platform: ActionPlatform | null;
  impact_level: ImpactLevel | null;
  parameters_schema: Record<string, unknown> | null;
  tags?: string[];
  /** Nombre d'exécutions (affiché si disponible, Task 1.1). */
  execution_count?: number | null;
}

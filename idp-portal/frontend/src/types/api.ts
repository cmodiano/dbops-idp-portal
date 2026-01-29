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

export type ActionCategory = 'Provisioning' | 'Patching' | 'Administration' | 'Monitoring';
export type ActionEngine = 'Oracle' | 'SQL Server' | 'DB2';
export type ActionPlatform = 'AAP' | 'GitHub Actions' | 'Azure DevOps' | 'Terraform';
export type ActionStatus = 'draft' | 'published' | 'disabled';

export interface ActionCreate {
  name: string;
  description?: string | null;
  category: ActionCategory;
  engine: ActionEngine;
  platform: ActionPlatform;
  parameters_schema?: Record<string, unknown> | null;
  impact_rules?: Record<string, { level: 'low' | 'medium' | 'high' | 'critical' }> | null;
}

export interface ActionResponse {
  id: number;
  name: string;
  description: string | null;
  category: ActionCategory;
  engine: ActionEngine;
  platform: ActionPlatform;
  parameters_schema: Record<string, unknown> | null;
  impact_rules: Record<string, { level: string }> | null;
  status: ActionStatus;
  created_by: number | null;
  created_at: string;
  updated_at: string | null;
  tags?: string[];
}

export interface ActionDetail extends ActionResponse {
  rbac_policies: Record<string, unknown> | null;
  execution_steps: ExecutionStep[] | null;
  change_type_config: Record<string, ChangeType> | null;
}

// === Execution Steps Types (Story 2.2; Story 2.7 connector_type) ===

export type ExecutionStepType = 'prerequisite' | 'execution' | 'verification';
/** Story 2.8: CAB removed; only pre-approved supported. */
export type ChangeType = 'pre_approved';

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
  change_type_config: Record<string, ChangeType> | null;
}

// === RBAC Policies Types (Story 2.3) ===

export type UserProfileType = 'dba_applicatif' | 'dba_infrastructure' | 'client_business' | 'dbops';

export interface EnvironmentPermission {
  profiles: UserProfileType[];
  requires_approval: boolean;
  approver_profiles: UserProfileType[] | null;
}

export interface RbacPolicies {
  environments: Record<string, EnvironmentPermission>;
}

export interface RbacPoliciesUpdate {
  policies: RbacPolicies;
}

// === Status Transition Types (Story 2.4) ===

export type StatusTransition = 'publish' | 'disable' | 'enable';

export interface StatusUpdateRequest {
  transition: StatusTransition;
}

export interface ActionListItem {
  id: number;
  name: string;
  status: ActionStatus;
  category: ActionCategory;
  engine: ActionEngine;
  created_at: string;
  execution_count: number;
  tags?: string[];
}

export interface AdminActionsFilters {
  status?: ActionStatus;
  category?: ActionCategory;
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

export type ImpactLevel = 'low' | 'medium' | 'high' | 'critical';

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

/**
 * Subset of ActionDetail used for real-time preview in admin form.
 * Contains all fields needed to render ActionCard and ActionDrawerPreview.
 */
export interface ActionPreviewData {
  name: string;
  description: string | null;
  category: ActionCategory | null;
  engine: ActionEngine | null;
  platform: ActionPlatform | null;
  impact_level: ImpactLevel | null;
  parameters_schema: Record<string, unknown> | null;
  tags?: string[];
  /** Nombre d'exécutions (affiché si disponible, Task 1.1). */
  execution_count?: number | null;
}

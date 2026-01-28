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
}

export interface ActionDetail extends ActionResponse {
  rbac_policies: Record<string, unknown> | null;
  execution_steps: ExecutionStep[] | null;
  change_type_config: Record<string, ChangeType> | null;
}

// === Execution Steps Types (Story 2.2) ===

export type ExecutionStepType = 'prerequisite' | 'execution' | 'verification';
export type ChangeType = 'pre_approved' | 'cab';

export interface ExecutionStep {
  order: number;
  name: string;
  type: ExecutionStepType;
  is_servicenow_change: boolean;
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

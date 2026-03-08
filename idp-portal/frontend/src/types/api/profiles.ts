// === Profile Types (Story 2.9, FR25a) ===

export interface ProfileCreate {
  name: string;
  description?: string | null;
  ad_group: string;
  is_admin?: boolean;
  is_auditor?: boolean;
  is_approver?: boolean;  // Story 57.14
}

export interface ProfileUpdate {
  name?: string | null;
  description?: string | null;
  ad_group?: string | null;
  is_admin?: boolean | null;
  is_auditor?: boolean | null;
  is_approver?: boolean | null;  // Story 57.14
}

export interface ProfileResponse {
  id: number;
  name: string;
  description: string | null;
  ad_group: string;
  is_admin: boolean;
  is_auditor: boolean;
  is_approver: boolean;  // Story 57.14
  created_at: string;
  updated_at: string;
  // Story 64.13: IaC drift tracking
  last_synced_at?: string | null;
  last_synced_hash?: string | null;
}

export interface ProfileListItem {
  id: number;
  name: string;
  ad_group: string;
  is_admin: boolean;
  is_auditor: boolean;
  is_approver: boolean;  // Story 57.14
  permission_count: number;
  created_at: string;
  updated_at?: string | null;
  // Story 64.13: IaC drift tracking
  last_synced_at?: string | null;
  last_synced_hash?: string | null;
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
  /** Story 23.7 - Filter targets by inventory attributes (e.g., engine_type: ['oracle']). */
  filter_by_attribute?: Record<string, string[]> | null;
  /** Story 25.6 - Exclusion patterns (deny explicit). Applied after inclusion rules. */
  exclusion_patterns?: string[] | null;
}

export interface ProfileTargetPermissionsResponse {
  targets_type: ProfileTargetsType;
  target_names: string[];
  target_patterns: string[];
  /** Story 23.7 - Filter targets by inventory attributes (e.g., engine_type: ['oracle']). */
  filter_by_attribute?: Record<string, string[]> | null;
  /** Story 25.6 - Exclusion patterns (deny explicit). Applied after inclusion rules. */
  exclusion_patterns?: string[];
}

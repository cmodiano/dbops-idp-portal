/**
 * Story 28.4: Business rule policy catalogue types.
 */

import type { PaginationInfo } from './common';
import type { BusinessRulePoliciesData } from './catalog';

/** Business rule policy list item (from GET /api/v1/admin/business-rule-policies/). */
export interface BusinessRulePolicyListItem {
  id: number;
  name: string;
  description: string | null;
  is_active: boolean;
  step_type: string | null;
  created_at: string;
  updated_at: string;
}

/** Business rule policy detail (from GET /api/v1/admin/business-rule-policies/{id}/). */
export interface BusinessRulePolicyDetail extends BusinessRulePolicyListItem {
  policy_json: BusinessRulePoliciesData;
  actions_count: number;
  created_by: number;
}

/** Payload for creating/updating a business rule policy. */
export interface BusinessRulePolicyPayload {
  name: string;
  description?: string | null;
  policy_json: BusinessRulePoliciesData;
  is_active?: boolean;
}

/** Paginated list response. */
export interface BusinessRulePolicyListResponse {
  data: BusinessRulePolicyListItem[];
  pagination: PaginationInfo | null;
}

/** Filters for listing business rule policies. */
export interface BusinessRulePolicyFilters {
  step_type?: string;
  is_active?: boolean;
  page?: number;
  page_size?: number;
}

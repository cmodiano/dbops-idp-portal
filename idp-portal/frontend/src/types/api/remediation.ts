import type { ExecutionStatusType } from './executions';

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

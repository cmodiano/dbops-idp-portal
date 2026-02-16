/**
 * Impact Rules JSON ↔ list conversion (Story 2.18, Task 1.2).
 * Build/parse impact_rules (object with environment keys) for the visual editor.
 */

import type { ImpactLevel, ImpactRuleDefinition } from '../types/api';

/** JSON object format stored in ACTIONS_CATALOG.impact_rules (CLOB). */
export type ImpactRulesJson = Record<string, { level: ImpactLevel; criteria?: string | null }>;

const VALID_LEVELS: ImpactLevel[] = ['low', 'medium', 'high', 'critical'];

/**
 * Convert backend impact_rules (JSON object) to list of ImpactRuleDefinition for the editor.
 * Handles existing actions and empty/null rules.
 *
 * @example
 * Input: {"DEV": {"level": "low", "criteria": "..."}, "PROD": {"level": "high"}}
 * Output: [{environment: "DEV", level: "low", criteria: "..."}, {environment: "PROD", level: "high", criteria: null}]
 */
export function impactRulesToList(rules: ImpactRulesJson | null | undefined): ImpactRuleDefinition[] {
  if (!rules || typeof rules !== 'object') {
    return [];
  }

  const list: ImpactRuleDefinition[] = [];
  for (const environment of Object.keys(rules)) {
    const rule = rules[environment];
    if (!rule || typeof rule !== 'object') continue;

    const levelStr = rule.level;
    // Validate level is one of the allowed values
    const level: ImpactLevel = VALID_LEVELS.includes(levelStr as ImpactLevel)
      ? (levelStr as ImpactLevel)
      : 'low';

    list.push({
      // Deterministic ID based on environment (unique per action)
      id: `rule-${environment}`,
      environment,
      level,
      criteria: rule.criteria ?? null,
    });
  }
  return list;
}

/**
 * Convert list of ImpactRuleDefinition to impact_rules (JSON object) for backend.
 * Produces { "ENV": {"level": "...", "criteria": "..."}, ... } accepted by backend.
 *
 * @example
 * Input: [{environment: "DEV", level: "low", criteria: "..."}, {environment: "PROD", level: "high", criteria: null}]
 * Output: {"DEV": {"level": "low", "criteria": "..."}, "PROD": {"level": "high"}}
 */
export function listToImpactRules(list: ImpactRuleDefinition[]): ImpactRulesJson | null {
  if (!list.length) {
    return null;
  }

  const result: ImpactRulesJson = {};
  for (const rule of list) {
    const env = (rule.environment || '').trim();
    if (!env) continue;

    const entry: { level: ImpactLevel; criteria?: string | null } = {
      level: rule.level || 'low',
    };
    // Only include criteria if non-empty
    if (rule.criteria && rule.criteria.trim()) {
      entry.criteria = rule.criteria.trim();
    }
    result[env] = entry;
  }

  if (Object.keys(result).length === 0) {
    return null;
  }
  return result;
}

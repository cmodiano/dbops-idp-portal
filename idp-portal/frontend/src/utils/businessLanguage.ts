/**
 * Business-friendly language utilities (Story 7.1, AC2).
 *
 * Replaces technical jargon with accessible terms for business users.
 * The goal is to make the portal feel like a "black box" - users see what actions do,
 * not how they work internally.
 *
 * Story 30.9 (PERF-3): Regex patterns are pre-compiled at module level
 * instead of being recreated on every function call (~70 patterns).
 */

/** Mapping of technical terms to business-friendly equivalents (Story 7.1). */
const TECHNICAL_TERMS_MAP: Record<string, string> = {
  // Exact word replacements (case-insensitive)
  pipeline: 'processus automatique',
  playbook: 'action',
  webhook: 'notification automatique',
  template: 'modele',
  inventory: 'liste des serveurs',
  job: 'tache',
  workflow: 'enchainement',
  vault: 'coffre-fort de secrets',
  credential: 'acces securise',
  credentials: 'acces securises',
  // Additional technical terms
  ansible: 'automatisation',
  terraform: 'infrastructure',
  api: 'interface',
  endpoint: "point d'acces",
  script: 'programme',
  deploy: 'deployer',
  deployment: 'deploiement',
  rollback: 'retour arriere',
  instance: 'serveur',
  cluster: 'groupe de serveurs',
  node: 'serveur',
  container: 'environnement isole',
  docker: 'conteneur',
  kubernetes: 'orchestrateur',
  k8s: 'orchestrateur',
  yaml: 'configuration',
  json: 'donnees',
  config: 'configuration',
  parameter: 'option',
  parameters: 'options',
  execute: 'lancer',
  execution: 'lancement',
  trigger: 'declencher',
  cron: 'planification',
  scheduler: 'planificateur',
  backend: 'systeme',
  frontend: 'interface',
  database: 'base de donnees',
  db: 'base de donnees',
  query: 'requete',
  schema: 'structure',
  migration: 'mise a jour',
  patch: 'correctif',
  patching: 'mise a jour',
  provisioning: 'creation',
  decommission: 'retrait',
  monitoring: 'surveillance',
  alert: 'alerte',
  log: 'journal',
  logs: 'journaux',
  debug: 'diagnostic',
  error: 'erreur',
  exception: 'erreur',
  timeout: 'delai depasse',
  retry: 'nouvel essai',
  ssh: 'connexion securisee',
  ssl: 'securise',
  tls: 'securise',
  token: "jeton d'acces",
  auth: 'authentification',
  authentication: 'authentification',
  authorization: 'autorisation',
  rbac: 'permissions',
  role: 'role',
  permission: 'autorisation',
  admin: 'administrateur',
  sudo: 'privileges eleves',
  root: 'administrateur systeme',
};

/**
 * Pre-compiled regex patterns for sanitizeDescription (Story 30.9, PERF-3).
 * Compiled once at module load instead of on every function call (~60 patterns).
 * Note: 'g' flag is safe here since .replace() resets lastIndex automatically
 */
const SANITIZE_PATTERNS: ReadonlyArray<readonly [RegExp, string]> = Object.entries(
  TECHNICAL_TERMS_MAP,
).map(([technical, friendly]) => [new RegExp(`\\b${technical}\\b`, 'gi'), friendly] as const);

/**
 * Pre-compiled regex patterns for containsTechnicalTerms (Story 30.9, PERF-3).
 * Uses 'i' flag (not 'g') since we only need to test for presence.
 * Note: 'g' flag is intentionally omitted to avoid stateful regex behavior with .test()
 */
const DETECT_PATTERNS: ReadonlyArray<RegExp> = Object.keys(TECHNICAL_TERMS_MAP).map(
  (term) => new RegExp(`\\b${term}\\b`, 'i'),
);

/**
 * Sanitize a description by replacing technical terms with business-friendly equivalents.
 *
 * @param text - The original text (description, label, etc.)
 * @returns Text with technical terms replaced by accessible language
 *
 * @example
 * sanitizeDescription("Execute the Ansible playbook to deploy the application")
 * // => "Lancer l'action pour deployer l'application"
 */
export function sanitizeDescription(text: string | null | undefined): string {
  if (!text) return '';

  let result = text;

  for (const [pattern, replacement] of SANITIZE_PATTERNS) {
    result = result.replace(pattern, replacement);
  }

  return result;
}

/**
 * Check if text contains technical jargon that should be simplified.
 *
 * @param text - The text to check
 * @returns true if the text contains technical terms
 */
export function containsTechnicalTerms(text: string | null | undefined): boolean {
  if (!text) return false;

  return DETECT_PATTERNS.some((regex) => regex.test(text));
}

/**
 * validateStepReferences — Validation des références de steps dans les templates input_mapping (Story 57.20).
 *
 * Extrait les step_id référencés dans les expressions Jinja2 {{ steps.<step_id>.<field> }}
 * et vérifie qu'ils existent dans le workflow courant.
 */

/**
 * Extrait les step_id uniques référencés dans une valeur de template Jinja2.
 */
export function extractStepReferences(value: string): string[] {
  const matches = value.matchAll(/\{\{\s*steps\.([a-zA-Z0-9_-]+)\./g);
  const refs: string[] = [];
  for (const match of matches) {
    if (!refs.includes(match[1])) {
      refs.push(match[1]);
    }
  }
  return refs;
}

/**
 * Retourne les step_id référencés dans la valeur qui n'existent pas dans availableStepIds.
 */
export function validateStepReferences(
  value: string,
  availableStepIds: string[],
): string[] {
  const refs = extractStepReferences(value);
  return refs.filter((ref) => !availableStepIds.includes(ref));
}

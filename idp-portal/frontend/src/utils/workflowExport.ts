/**
 * Workflow export/import utilities (Story 16.8).
 *
 * - Export JSON/YAML/PNG from React Flow nodes & edges
 * - Import JSON/YAML with validation
 * - Filename sanitization & date formatting
 */

import yaml from 'js-yaml';
import type { WorkflowStep } from '../types/api';

// ── Types ───────────────────────────────────────────────────────────────────

export interface WorkflowExport {
  version: string;
  workflow: {
    name: string;
    description: string | null;
    tags: string[];
    steps: WorkflowStep[];
  };
}

export interface WorkflowImportResult {
  valid: boolean;
  data: WorkflowExport | null;
  errors: string[];
}

export interface WorkflowMetadata {
  name: string;
  description: string | null;
  tags: string[];
}

// ── Helpers ─────────────────────────────────────────────────────────────────

/** Sanitize filename: replace forbidden characters with underscore */
export function sanitizeFilename(name: string): string {
  return name
    .replace(/[/\\:*?"<>|]/g, '_')
    .replace(/\s+/g, '_')
    .replace(/_+/g, '_')
    .replace(/^_|_$/g, '')
    .slice(0, 100) || 'workflow';
}

/** Format date for filenames: YYYY-MM-DD_HH-mm-ss */
export function formatDateForFilename(date: Date): string {
  const pad = (n: number) => n.toString().padStart(2, '0');
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}_${pad(date.getHours())}-${pad(date.getMinutes())}-${pad(date.getSeconds())}`;
}

/** Trigger file download in browser */
function downloadBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

// ── Build export object ────────────────────────────────────────────────────

/** Build WorkflowExport structure from steps + metadata */
export function buildWorkflowExport(
  steps: WorkflowStep[],
  metadata: WorkflowMetadata,
): WorkflowExport {
  return {
    version: '1.0',
    workflow: {
      name: metadata.name,
      description: metadata.description ?? null,
      tags: metadata.tags ?? [],
      steps: steps.map((s) => {
        // Story 65.4: parallel_group has a different schema
        if (s.step_type === 'parallel_group') {
          return {
            step_id: s.step_id ?? null,
            step_type: 'parallel_group' as const,
            name: s.name ?? null,
            parallel_steps: s.parallel_steps ?? [],
            on_all_success_step_id: s.on_all_success_step_id ?? null,
            on_any_error_step_id: s.on_any_error_step_id ?? null,
            order: s.order,
          };
        }
        // Story 67.4: on_success_step_ids / on_error_step_ids, join_policy
        const successIds = s.on_success_step_ids ?? [];
        const errorIds = s.on_error_step_ids ?? [];
        return {
          step_id: s.step_id ?? null,
          step_type: s.step_type ?? 'platform', // Story 65.4: toujours inclure step_type
          referenced_action_id: s.referenced_action_id,
          name: s.name ?? null,
          on_success_step_ids: successIds,
          on_error_step_ids: errorIds,
          ...(s.join_policy ? { join_policy: s.join_policy } : {}),
          retry_enabled: s.retry_enabled ?? false,
          retry_max_attempts: s.retry_max_attempts ?? null,
          retry_interval_seconds: s.retry_interval_seconds ?? null,
          retry_backoff_multiplier: s.retry_backoff_multiplier ?? null,
          order: s.order, // Optional field at end
        };
      }),
    },
  };
}

// ── Export JSON ──────────────────────────────────────────────────────────────

/** Export workflow as JSON and trigger download */
export function exportWorkflowAsJSON(
  steps: WorkflowStep[],
  metadata: WorkflowMetadata,
): void {
  const exportObj = buildWorkflowExport(steps, metadata);
  const jsonString = JSON.stringify(exportObj, null, 2);
  const blob = new Blob([jsonString], { type: 'application/json' });
  const filename = `${sanitizeFilename(metadata.name)}_${formatDateForFilename(new Date())}.json`;
  downloadBlob(blob, filename);
}

// ── Export YAML ─────────────────────────────────────────────────────────────

/** Export workflow as YAML and trigger download */
export function exportWorkflowAsYAML(
  steps: WorkflowStep[],
  metadata: WorkflowMetadata,
): void {
  const exportObj = buildWorkflowExport(steps, metadata);
  const yamlString = yaml.dump(exportObj, {
    indent: 2,
    lineWidth: 120,
    noRefs: true,
    sortKeys: false,
  });
  const blob = new Blob([yamlString], { type: 'text/yaml' });
  const filename = `${sanitizeFilename(metadata.name)}_${formatDateForFilename(new Date())}.yaml`;
  downloadBlob(blob, filename);
}

// ── Export Image ────────────────────────────────────────────────────────────

/** Export workflow canvas as PNG image and trigger download */
export async function exportWorkflowAsImage(
  reactFlowWrapper: HTMLDivElement,
  workflowName: string,
): Promise<void> {
  const html2canvas = (await import('html2canvas')).default;

  const sourceCanvas = await html2canvas(reactFlowWrapper, {
    backgroundColor: '#ffffff',
    scale: 2,
    logging: false,
    useCORS: true,
  });

  // Create final canvas with header + legend
  const headerHeight = 100;
  const finalCanvas = document.createElement('canvas');
  finalCanvas.width = sourceCanvas.width;
  finalCanvas.height = sourceCanvas.height + headerHeight;

  const ctx = finalCanvas.getContext('2d');
  if (!ctx) return;

  // White background
  ctx.fillStyle = '#ffffff';
  ctx.fillRect(0, 0, finalCanvas.width, finalCanvas.height);

  // Header: workflow name
  ctx.font = 'bold 32px sans-serif';
  ctx.fillStyle = '#000000';
  ctx.fillText(workflowName, 20, 45);

  // Legend
  ctx.font = '18px sans-serif';
  ctx.fillStyle = '#52c41a';
  ctx.fillText('● Succès', 20, 80);
  ctx.fillStyle = '#ff4d4f';
  ctx.fillText('● Erreur', 180, 80);
  ctx.fillStyle = '#1890ff';
  ctx.fillText('↻ Retry activé', 340, 80);

  // Draw captured canvas below header
  ctx.drawImage(sourceCanvas, 0, headerHeight);

  // Download as PNG
  return new Promise<void>((resolve, reject) => {
    finalCanvas.toBlob((blob) => {
      if (!blob) {
        reject(new Error('Échec de la génération de l\'image PNG'));
        return;
      }
      const filename = `${sanitizeFilename(workflowName)}_${formatDateForFilename(new Date())}.png`;
      downloadBlob(blob, filename);
      resolve();
    }, 'image/png');
  });
}

// ── Validation ──────────────────────────────────────────────────────────────

/** Validate a parsed workflow export object. Returns errors list. */
export function validateWorkflowImport(data: unknown): string[] {
  const errors: string[] = [];

  if (typeof data !== 'object' || data === null) {
    return ['Le fichier ne contient pas un objet valide.'];
  }

  const obj = data as Record<string, unknown>;

  // Version check
  if (obj.version !== '1.0') {
    errors.push(`Version "${String(obj.version ?? 'manquante')}" non supportée. Version attendue : "1.0".`);
  }

  // Workflow object
  if (typeof obj.workflow !== 'object' || obj.workflow === null) {
    return [...errors, 'Le champ "workflow" est manquant ou invalide.'];
  }

  const wf = obj.workflow as Record<string, unknown>;

  // Name
  if (typeof wf.name !== 'string' || wf.name.trim().length === 0) {
    errors.push('Le nom du workflow est requis (workflow.name).');
  } else if (wf.name.length > 200) {
    errors.push('Le nom du workflow ne peut pas dépasser 200 caractères.');
  }

  // Description (optional)
  if (wf.description !== undefined && wf.description !== null && typeof wf.description !== 'string') {
    errors.push('Le champ "description" doit être une chaîne de caractères ou null.');
  }

  // Tags (optional)
  if (wf.tags !== undefined && wf.tags !== null) {
    if (!Array.isArray(wf.tags)) {
      errors.push('Le champ "tags" doit être un tableau.');
    } else if (wf.tags.some((t: unknown) => typeof t !== 'string')) {
      errors.push('Tous les tags doivent être des chaînes de caractères.');
    }
  }

  // Steps
  if (!Array.isArray(wf.steps)) {
    errors.push('Le champ "steps" est requis et doit être un tableau.');
    return errors;
  }

  if (wf.steps.length === 0) {
    errors.push('Au moins une étape est requise dans le workflow.');
    return errors;
  }

  if (wf.steps.length > 100) {
    errors.push('Le workflow ne peut pas contenir plus de 100 étapes.');
  }

  // Validate each step
  const stepIds = new Set<string>();
  const allStepIds: string[] = [];

  (wf.steps as unknown[]).forEach((step: unknown, i: number) => {
    if (typeof step !== 'object' || step === null) {
      errors.push(`Étape ${i + 1} : doit être un objet.`);
      return;
    }
    const s = step as Record<string, unknown>;

    // step_id
    if (typeof s.step_id !== 'string' || s.step_id.length === 0) {
      errors.push(`Étape ${i + 1} : "step_id" est requis.`);
    } else {
      if (stepIds.has(s.step_id)) {
        errors.push(`Étape ${i + 1} : "step_id" en doublon : "${s.step_id}".`);
      }
      stepIds.add(s.step_id);
      allStepIds.push(s.step_id);
    }

    // Story 65.4: pour parallel_group, validation spécifique (pas de referenced_action_id requis)
    if (s.step_type === 'parallel_group') {
      if (!Array.isArray(s.parallel_steps) || s.parallel_steps.length < 2) {
        errors.push(`Étape ${i + 1} : "parallel_steps" doit contenir au moins 2 step_id.`);
      } else if (s.parallel_steps.some((id: unknown) => typeof id !== 'string' || (id as string).length === 0)) {
        errors.push(`Étape ${i + 1} : "parallel_steps" doit contenir des strings non-vides.`);
      } else if (new Set(s.parallel_steps).size !== (s.parallel_steps as string[]).length) {
        errors.push(`Étape ${i + 1} : "parallel_steps" contient des step_id dupliqués.`);
      }
    } else {
      // referenced_action_id
      if (typeof s.referenced_action_id !== 'number' || s.referenced_action_id < 1 || !Number.isInteger(s.referenced_action_id)) {
        errors.push(`Étape ${i + 1} : "referenced_action_id" doit être un entier positif.`);
      }

      // Retry validation
      if (s.retry_enabled === true) {
        if (typeof s.retry_max_attempts !== 'number' || s.retry_max_attempts < 1) {
          errors.push(`Étape ${i + 1} : "retry_max_attempts" doit être >= 1 si retry est activé.`);
        }
        if (typeof s.retry_interval_seconds !== 'number' || s.retry_interval_seconds < 1) {
          errors.push(`Étape ${i + 1} : "retry_interval_seconds" doit être >= 1 si retry est activé.`);
        }
        if (typeof s.retry_backoff_multiplier !== 'number' || s.retry_backoff_multiplier < 1.0) {
          errors.push(`Étape ${i + 1} : "retry_backoff_multiplier" doit être >= 1.0 si retry est activé.`);
        }
      }
    }

    // name (optional but should be string or null)
    if (s.name !== undefined && s.name !== null && typeof s.name !== 'string') {
      errors.push(`Étape ${i + 1} : "name" doit être une chaîne de caractères ou null.`);
    }
  });

  // Build step_id -> step lookup for member type checks
  const stepById = new Map<string, Record<string, unknown>>();
  (wf.steps as Record<string, unknown>[]).forEach((st) => {
    const sid = st.step_id as string;
    if (typeof sid === 'string' && sid) stepById.set(sid, st);
  });

  // Cross-step reference validation
  (wf.steps as Record<string, unknown>[]).forEach((s, i) => {
    if (s.step_type === 'parallel_group') {
      // Story 65.4: valider les références dans parallel_group
      if (Array.isArray(s.parallel_steps)) {
        (s.parallel_steps as string[]).forEach((pid) => {
          if (!stepIds.has(pid)) {
            errors.push(`Étape ${i + 1} : parallel_steps référence un step_id inexistant : "${pid}".`);
          }
          if (pid === s.step_id) {
            errors.push(`Étape ${i + 1} : auto-référence interdite dans parallel_steps (step_id = "${pid}").`);
          }
          const refStep = stepById.get(pid);
          const refType = (refStep?.step_type as string) ?? 'platform';
          if (refType === 'parallel_group') {
            errors.push(`Étape ${i + 1} : parallel_steps ne peut pas contenir de parallel_group imbriqué ("${pid}").`);
          }
          if (refType === 'gate') {
            errors.push(`Étape ${i + 1} : parallel_steps ne peut pas contenir de step gate ("${pid}").`);
          }
        });
      }
      if (typeof s.on_all_success_step_id === 'string' && s.on_all_success_step_id) {
        if (!stepIds.has(s.on_all_success_step_id)) {
          errors.push(`Étape ${i + 1} : "on_all_success_step_id" référence un step_id inexistant : "${s.on_all_success_step_id}".`);
        }
        if (s.on_all_success_step_id === s.step_id) {
          errors.push(`Étape ${i + 1} : auto-référence interdite (on_all_success_step_id = step_id).`);
        }
      }
      if (typeof s.on_any_error_step_id === 'string' && s.on_any_error_step_id) {
        if (!stepIds.has(s.on_any_error_step_id)) {
          errors.push(`Étape ${i + 1} : "on_any_error_step_id" référence un step_id inexistant : "${s.on_any_error_step_id}".`);
        }
        if (s.on_any_error_step_id === s.step_id) {
          errors.push(`Étape ${i + 1} : auto-référence interdite (on_any_error_step_id = step_id).`);
        }
      }
    } else {
      const successTargets: string[] = Array.isArray(s.on_success_step_ids)
        ? (s.on_success_step_ids as string[]).filter((id): id is string => typeof id === 'string' && id.length > 0)
        : [];
      for (const tid of successTargets) {
        if (!stepIds.has(tid)) {
          errors.push(`Étape ${i + 1} : "on_success_step_ids" référence un step_id inexistant : "${tid}".`);
        }
        if (tid === s.step_id) {
          errors.push(`Étape ${i + 1} : auto-référence interdite (on_success_step_ids = step_id).`);
        }
      }
      const errorTargets: string[] = Array.isArray(s.on_error_step_ids)
        ? (s.on_error_step_ids as string[]).filter((id): id is string => typeof id === 'string' && id.length > 0)
        : [];
      for (const tid of errorTargets) {
        if (!stepIds.has(tid)) {
          errors.push(`Étape ${i + 1} : "on_error_step_ids" référence un step_id inexistant : "${tid}".`);
        }
        if (tid === s.step_id) {
          errors.push(`Étape ${i + 1} : auto-référence interdite (on_error_step_ids = step_id).`);
        }
      }
      // Story 67.4: join_policy
      if (s.join_policy !== undefined && s.join_policy !== null) {
        const validPolicies = ['all_success', 'one_success', 'all_done'];
        if (typeof s.join_policy !== 'string' || !validPolicies.includes(s.join_policy)) {
          errors.push(
            `Étape ${i + 1} : "join_policy" doit être l'une de : ${validPolicies.join(', ')}. Reçu : "${s.join_policy}".`,
          );
        }
      }
    }
  });

  return errors;
}

// ── Parse file ──────────────────────────────────────────────────────────────

/** Parse a workflow file (JSON or YAML) and validate it */
export function parseWorkflowFile(
  content: string,
  fileExtension: string,
): WorkflowImportResult {
  let parsed: unknown;

  // Parse
  try {
    if (fileExtension === '.json') {
      parsed = JSON.parse(content);
    } else if (fileExtension === '.yaml' || fileExtension === '.yml') {
      parsed = yaml.load(content);
    } else {
      return { valid: false, data: null, errors: [`Extension de fichier non supportée : "${fileExtension}". Utilisez .json, .yaml ou .yml.`] };
    }
  } catch (e) {
    const errorMessage = e instanceof Error ? e.message : 'Erreur inconnue';
    return { valid: false, data: null, errors: [`Erreur de parsing ${fileExtension.toUpperCase()} : ${errorMessage}`] };
  }

  // Validate
  const validationErrors = validateWorkflowImport(parsed);
  if (validationErrors.length > 0) {
    return { valid: false, data: null, errors: validationErrors };
  }

  // Cast to WorkflowExport — safe after validation
  const exportData = parsed as WorkflowExport;

  // Normalize steps: ensure all optional fields have defaults
  const normalizedSteps: WorkflowStep[] = exportData.workflow.steps.map((step, index) => {
    const base = {
      order: typeof step.order === 'number' ? step.order : index + 1,
      step_id: step.step_id ?? null,
      name: step.name ?? null,
      step_type: step.step_type ?? 'platform',
    };
    // Story 65.4: parallel_group normalisation
    if (step.step_type === 'parallel_group') {
      return {
        ...base,
        parallel_steps: Array.isArray(step.parallel_steps) ? step.parallel_steps : [],
        on_all_success_step_id: step.on_all_success_step_id ?? null,
        on_any_error_step_id: step.on_any_error_step_id ?? null,
      };
    }
    return {
      ...base,
      referenced_action_id: step.referenced_action_id,
      on_success_step_ids: step.on_success_step_ids ?? [],
      on_error_step_ids: step.on_error_step_ids ?? [],
      retry_enabled: step.retry_enabled ?? false,
      retry_max_attempts: step.retry_max_attempts ?? null,
      retry_interval_seconds: step.retry_interval_seconds ?? null,
      retry_backoff_multiplier: step.retry_backoff_multiplier ?? null,
    };
  });

  return {
    valid: true,
    data: {
      version: exportData.version,
      workflow: {
        name: exportData.workflow.name,
        description: exportData.workflow.description ?? null,
        tags: Array.isArray(exportData.workflow.tags) ? exportData.workflow.tags : [],
        steps: normalizedSteps,
      },
    },
    errors: [],
  };
}

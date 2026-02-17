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
      // MEDIUM-1 FIX: Reorder fields to match JSON Schema documentation
      steps: steps.map((s) => ({
        step_id: s.step_id ?? null,
        referenced_action_id: s.referenced_action_id,
        name: s.name ?? null,
        on_success_step_id: s.on_success_step_id ?? null,
        on_error_step_id: s.on_error_step_id ?? null,
        retry_enabled: s.retry_enabled ?? false,
        retry_max_attempts: s.retry_max_attempts ?? null,
        retry_interval_seconds: s.retry_interval_seconds ?? null,
        retry_backoff_multiplier: s.retry_backoff_multiplier ?? null,
        order: s.order, // Optional field at end
      })),
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
        // HIGH-3 FIX: Reject instead of silently resolving
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

    // referenced_action_id
    if (typeof s.referenced_action_id !== 'number' || s.referenced_action_id < 1 || !Number.isInteger(s.referenced_action_id)) {
      errors.push(`Étape ${i + 1} : "referenced_action_id" doit être un entier positif.`);
    }

    // name (optional but should be string or null)
    if (s.name !== undefined && s.name !== null && typeof s.name !== 'string') {
      errors.push(`Étape ${i + 1} : "name" doit être une chaîne de caractères ou null.`);
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
  });

  // Cross-step reference validation
  (wf.steps as Record<string, unknown>[]).forEach((s, i) => {
    if (typeof s.on_success_step_id === 'string' && s.on_success_step_id) {
      if (!stepIds.has(s.on_success_step_id)) {
        errors.push(`Étape ${i + 1} : "on_success_step_id" référence un step_id inexistant : "${s.on_success_step_id}".`);
      }
      if (s.on_success_step_id === s.step_id) {
        errors.push(`Étape ${i + 1} : auto-référence interdite (on_success_step_id = step_id).`);
      }
    }
    if (typeof s.on_error_step_id === 'string' && s.on_error_step_id) {
      if (!stepIds.has(s.on_error_step_id)) {
        errors.push(`Étape ${i + 1} : "on_error_step_id" référence un step_id inexistant : "${s.on_error_step_id}".`);
      }
      if (s.on_error_step_id === s.step_id) {
        errors.push(`Étape ${i + 1} : auto-référence interdite (on_error_step_id = step_id).`);
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
  const normalizedSteps: WorkflowStep[] = exportData.workflow.steps.map((step, index) => ({
    order: typeof step.order === 'number' ? step.order : index + 1,
    step_id: step.step_id ?? null,
    referenced_action_id: step.referenced_action_id,
    name: step.name ?? null,
    on_success_step_id: step.on_success_step_id ?? null,
    on_error_step_id: step.on_error_step_id ?? null,
    retry_enabled: step.retry_enabled ?? false,
    retry_max_attempts: step.retry_max_attempts ?? null,
    retry_interval_seconds: step.retry_interval_seconds ?? null,
    retry_backoff_multiplier: step.retry_backoff_multiplier ?? null,
  }));

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

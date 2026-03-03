/**
 * workflowStepLabels — Fonctions utilitaires centralisées pour résoudre les labels lisibles
 * des étapes de workflow (Story 57.19).
 *
 * Utilisé par GateStepConfig (context_from), StepConfigPanel (step_id), SortableStepCard (branches).
 */

import type { WorkflowStep } from '../types/api/catalog';

/** Minimal step shape accepted by getStepLabel (works with both WorkflowStep and WorkflowStepNodeData). */
export interface StepLabelInput {
  name?: string | null;
  order?: number;
  step_type?: string;
  step_id?: string | null;
  action_name?: string | null;
  integration_type?: string | null;
  operation?: string | null;
  policy_id?: number | null;
  gate_type?: string | null;
  method?: string | null;
  url?: string | null;
}

/**
 * Génère un label lisible pour une étape de workflow.
 * Priorité : name > label généré par step_type.
 */
export function getStepLabel(step: StepLabelInput): string {
  if (step.name) return step.name;

  const prefix = step.order != null ? `Étape ${step.order}` : 'Étape';

  switch (step.step_type) {
    case 'platform':
      return step.action_name
        ? `${prefix} — ${step.action_name}`
        : prefix;
    case 'service_call':
      return `${prefix} — ${step.integration_type ?? 'service'} / ${step.operation ?? '?'}`;
    case 'evaluation':
      return `${prefix} — Évaluation policy #${step.policy_id ?? '?'}`;
    case 'gate':
      return step.gate_type === 'approval'
        ? `${prefix} — Approbation`
        : `${prefix} — Fenêtre maintenance`;
    case 'http_request':
      return `${prefix} — ${step.method ?? 'GET'} ${step.url ?? ''}`.trim();
    case 'schedule_execution':
      return step.action_name
        ? `${prefix} — Planifier ${step.action_name}`
        : `${prefix} — Planification`;
    default:
      return prefix;
  }
}

/**
 * Génère les options pour un Select/dropdown de sélection d'étapes.
 */
export function getStepOptions(
  steps: Array<WorkflowStep | StepLabelInput>,
  excludeStepId?: string | null,
): { value: string; label: string }[] {
  return steps
    .filter((s): s is typeof s & { step_id: string } => {
      const id = s.step_id;
      return !!id && id !== excludeStepId;
    })
    .map((s) => ({
      value: s.step_id,
      label: getStepLabel(s),
    }));
}

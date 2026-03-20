/**
 * Workflow Validation Utilities — Story 26.5 AC2
 *
 * Extracted from WorkflowBuilderCanvas.tsx to separate concerns.
 * Validates workflow graph structure: nodes, edges, reachability, loops.
 *
 * Story 84.3 (AC6): getStepTypeErrors lit les required_fields depuis les capabilities backend.
 * Le switch métier sur les champs requis simples est supprimé — seule la validation complexe
 * de schedule_execution (schedule_config, schedule_source…) reste en frontend.
 */
import type { Node, Edge } from '@xyflow/react';
import { START_NODE_ID, END_NODE_ID } from './workflowConversion';
import type { WorkflowStepNodeData } from '../components/admin/WorkflowStepNode';
import type { WorkflowStepCapability } from '../services/capabilities_service';

/** Validation error or warning for a specific node. */
export interface ValidationError {
  nodeId: string;
  type: 'error' | 'warning';
  message: string;
}

/** Result of workflow graph validation. */
export interface ValidationResult {
  valid: boolean;
  errors: ValidationError[];
}

/**
 * Validate step configuration per type (Story 57.13, AC8 ; Story 84.3, AC6).
 *
 * Les champs requis simples sont dérivés de `stepTypeCapabilities` (backend-driven).
 * La validation complexe de schedule_execution reste en frontend.
 *
 * Si `stepTypeCapabilities` est absent, aucune erreur de champ n'est générée (résilient).
 */
function getStepTypeErrors(
  nodeId: string,
  data: WorkflowStepNodeData,
  stepTypeCapabilities?: WorkflowStepCapability[],
): ValidationError[] {
  // Backward compat: if step_type is not explicitly set, skip per-type validation
  if (!data.step_type) return [];
  const stepType = data.step_type;
  const errors: ValidationError[] = [];

  // Story 84.3 (AC6): champs requis dérivés du backend via required_fields
  const stepDef = stepTypeCapabilities?.find((s) => s.code === stepType);
  const requiredFields = (stepDef?.constraints?.required_fields ?? []) as Array<{
    field: string;
    message: string;
  }>;
  for (const { field, message } of requiredFields) {
    const value = data[field as keyof WorkflowStepNodeData];
    if (value === null || value === undefined || value === '') {
      errors.push({ nodeId, type: 'error', message });
    }
  }

  // Validation des champs requis pour les service_call de type notification (send_email / send_teams)
  if (stepType === 'service_call') {
    const inputMapping = (data.input_mapping ?? {}) as Record<string, unknown>;
    if (data.operation === 'send_email') {
      if (!inputMapping.recipient_email) {
        errors.push({ nodeId, type: 'error', message: "Adresse e-mail destinataire requise (recipient_email)" });
      }
      if (!inputMapping.subject) {
        errors.push({ nodeId, type: 'error', message: "Sujet de l'e-mail requis (subject)" });
      }
      if (!inputMapping.body) {
        errors.push({ nodeId, type: 'error', message: "Corps de l'e-mail requis (body)" });
      }
    } else if (data.operation === 'send_teams') {
      if (!inputMapping.webhook_url) {
        errors.push({ nodeId, type: 'error', message: "URL du webhook Teams requise (webhook_url)" });
      }
      if (!inputMapping.message && !inputMapping.title) {
        errors.push({ nodeId, type: 'error', message: "Message ou titre requis pour la notification Teams" });
      }
    }
  }

  // Story 84.3 (AC6): validation UI complexe — schedule_execution uniquement (non dérivable par required_fields)
  if (stepType === 'schedule_execution') {
    const config = data.schedule_config;
    if (!config) {
      errors.push({ nodeId, type: 'error', message: 'Configuration de planification requise' });
      return errors;
    }
    if (!config.schedule_source) {
      errors.push({ nodeId, type: 'error', message: 'Source de date requise (schedule_source)' });
      return errors;
    }
    if (config.schedule_source === 'parameter' && !config.schedule_parameter_name) {
      errors.push({ nodeId, type: 'error', message: "Nom du paramètre de date requis (schedule_parameter_name)" });
    }
    if (config.schedule_source === 'fixed_offset' && !config.fixed_offset) {
      errors.push({ nodeId, type: 'error', message: "Offset fixe requis (ex: +3d, +6h)" });
    }
    if (config.schedule_source === 'recurring' && !config.recurring_pattern?.pattern_type) {
      errors.push({ nodeId, type: 'error', message: "Type de pattern récurrent requis" });
    }
  }

  return errors;
}

/**
 * Validate workflow graph structure.
 *
 * Checks:
 * 1. At least one workflow node exists
 * 2. Every node has at least one output connection
 * 3. All nodes are reachable from start (no orphans)
 * 4. No infinite loops (cycle detection DFS)
 * 5. Step configuration per type (Story 57.13, AC8 ; Story 84.3, AC6)
 *
 * Story 84.3 (AC6): `stepTypeCapabilities` est optionnel.
 * Si absent, la validation de champs requis est silencieuse (résiliente).
 */
export function validateWorkflowGraph(
  nodes: Node[],
  edges: Edge[],
  stepTypeCapabilities?: WorkflowStepCapability[],
): ValidationResult {
  // Filter out start/end visual nodes for validation
  const workflowNodes = nodes.filter(
    (n) => n.id !== START_NODE_ID && n.id !== END_NODE_ID
  );
  const workflowEdges = edges.filter(
    (e) => e.source !== START_NODE_ID && e.target !== END_NODE_ID &&
          e.source !== END_NODE_ID && e.target !== START_NODE_ID
  );

  const errors: ValidationError[] = [];

  if (workflowNodes.length === 0) {
    return { valid: false, errors: [{ nodeId: '', type: 'error', message: 'Au moins une étape est requise' }] };
  }

  // 0. Check workflow has internal connections if multiple steps exist
  if (workflowNodes.length > 1 && workflowEdges.length === 0) {
    errors.push({
      nodeId: '',
      type: 'error',
      message: 'Aucune connexion entre les étapes du workflow',
    });
  }

  // 1. Check every node has at least one output connection (incl. edges to End node)
  workflowNodes.forEach((node) => {
    const hasSuccessEdge = edges.some((e) => e.source === node.id && e.sourceHandle === 'success');
    const hasErrorEdge = edges.some((e) => e.source === node.id && e.sourceHandle === 'error');

    if (!hasSuccessEdge && !hasErrorEdge) {
      errors.push({
        nodeId: node.id,
        type: 'warning',
        message: `Pas de chemin de sortie`,
      });
    }
  });

  // 2. Detect orphan nodes (not reachable from start) — use edges FROM START_NODE_ID as entry points
  if (workflowNodes.length > 1) {
    const reachableNodes = new Set<string>();

    // Find all workflow nodes directly connected from START_NODE_ID as entry points
    const startEdges = edges.filter((e) => e.source === START_NODE_ID);
    const queue = startEdges.map((e) => e.target).filter((id) => id !== END_NODE_ID);

    // BFS traversal from entry points through internal workflow edges
    while (queue.length > 0) {
      const current = queue.shift()!;
      if (reachableNodes.has(current)) continue;
      reachableNodes.add(current);

      workflowEdges
        .filter((e) => e.source === current)
        .forEach((e) => {
          if (!reachableNodes.has(e.target)) {
            queue.push(e.target);
          }
        });
    }

    workflowNodes.forEach((node) => {
      if (!reachableNodes.has(node.id)) {
        errors.push({
          nodeId: node.id,
          type: 'error',
          message: `Non atteignable depuis le début`,
        });
      }
    });
  }

  // 3. Detect infinite loops (DFS cycle detection)
  const visited = new Set<string>();
  const inStack = new Set<string>();
  const loopNodes = new Set<string>();

  function dfs(nodeId: string): boolean {
    if (inStack.has(nodeId)) {
      loopNodes.add(nodeId);
      return true;
    }
    if (visited.has(nodeId)) return false;

    visited.add(nodeId);
    inStack.add(nodeId);

    const outEdges = workflowEdges.filter((e) => e.source === nodeId);
    for (const edge of outEdges) {
      if (dfs(edge.target)) {
        loopNodes.add(nodeId);
      }
    }

    inStack.delete(nodeId);
    return false;
  }

  workflowNodes.forEach((node) => {
    if (!visited.has(node.id)) {
      dfs(node.id);
    }
  });

  loopNodes.forEach((nodeId) => {
    errors.push({
      nodeId,
      type: 'error',
      message: `Boucle infinie détectée`,
    });
  });

  // 4. Validate step configuration per type (Story 57.13, AC8 ; Story 84.3, AC6)
  workflowNodes.forEach((node) => {
    const data = node.data as unknown as WorkflowStepNodeData;
    const stepErrors = getStepTypeErrors(node.id, data, stepTypeCapabilities);
    errors.push(...stepErrors);
  });

  return {
    valid: errors.filter((e) => e.type === 'error').length === 0,
    errors,
  };
}

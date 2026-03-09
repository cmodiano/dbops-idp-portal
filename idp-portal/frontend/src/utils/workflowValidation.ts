/**
 * Workflow Validation Utilities — Story 26.5 AC2
 *
 * Extracted from WorkflowBuilderCanvas.tsx to separate concerns.
 * Validates workflow graph structure: nodes, edges, reachability, loops.
 */
import type { Node, Edge } from '@xyflow/react';
import { START_NODE_ID, END_NODE_ID } from './workflowConversion';
import type { WorkflowStepNodeData } from '../components/admin/WorkflowStepNode';

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
 * Validate step configuration per type (Story 57.13, AC8).
 * Checks required fields per step_type.
 */
function getStepTypeErrors(nodeId: string, data: WorkflowStepNodeData): ValidationError[] {
  // Backward compat: if step_type is not explicitly set, skip per-type validation
  if (!data.step_type) return [];
  const stepType = data.step_type;
  const errors: ValidationError[] = [];

  switch (stepType) {
    case 'platform':
      if (!data.action_id) {
        errors.push({ nodeId, type: 'error', message: 'Action requise pour un step de type Exécuter' });
      }
      break;
    case 'service_call':
      if (!data.integration_type) {
        errors.push({ nodeId, type: 'error', message: "Type d'intégration requis" });
      }
      if (!data.operation) {
        errors.push({ nodeId, type: 'error', message: 'Opération requise' });
      }
      break;
    case 'evaluation':
      if (!data.policy_id) {
        errors.push({ nodeId, type: 'error', message: 'Politique de règles métier requise' });
      }
      break;
    case 'gate':
      if (!data.gate_type) {
        errors.push({ nodeId, type: 'error', message: 'Type de gate requis (maintenance_window ou approval)' });
      }
      break;
    case 'http_request':
      if (!data.url) {
        errors.push({ nodeId, type: 'error', message: 'URL requise' });
      }
      if (!data.method) {
        errors.push({ nodeId, type: 'error', message: 'Méthode HTTP requise' });
      }
      break;
    case 'schedule_execution': {
      // referenced_action_id requis
      if (!data.action_id) {
        errors.push({ nodeId, type: 'error', message: 'Action cible requise pour le step de planification' });
      }
      const config = data.schedule_config;
      if (!config) {
        errors.push({ nodeId, type: 'error', message: 'Configuration de planification requise' });
        break;
      }
      if (!config.schedule_source) {
        errors.push({ nodeId, type: 'error', message: 'Source de date requise (schedule_source)' });
        break;
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
      break;
    }
    case 'parallel_group': {
      // Story 65.4: parallel_group doit avoir au moins 2 sous-steps distincts
      const ps = data.parallel_steps;
      if (!ps || ps.length < 2) {
        errors.push({
          nodeId,
          type: 'error',
          message: 'Un groupe parallèle doit contenir au moins 2 sous-steps (parallel_steps)',
        });
      } else if (new Set(ps).size !== ps.length) {
        errors.push({
          nodeId,
          type: 'error',
          message: 'parallel_steps ne doit pas contenir de doublons',
        });
      }
      break;
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
 * 5. Step configuration per type (Story 57.13, AC8)
 */
export function validateWorkflowGraph(nodes: Node[], edges: Edge[]): ValidationResult {
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

  // 4. Validate step configuration per type (Story 57.13, AC8)
  workflowNodes.forEach((node) => {
    const data = node.data as unknown as WorkflowStepNodeData;
    const stepErrors = getStepTypeErrors(node.id, data);
    errors.push(...stepErrors);
  });

  // 5. parallel_group: reject nested parallel_group/gate members; validate routing targets
  const nodeIds = new Set(workflowNodes.map((n) => n.id));
  workflowNodes.forEach((node) => {
    const data = node.data as unknown as WorkflowStepNodeData;
    if (data.step_type !== 'parallel_group') return;
    const ps = data.parallel_steps;
    if (!Array.isArray(ps)) return;

    ps.forEach((memberId) => {
      const memberNode = workflowNodes.find((n) => n.id === memberId);
      if (!memberNode) {
        errors.push({
          nodeId: node.id,
          type: 'error',
          message: `parallel_steps : le membre "${memberId}" n'existe pas`,
        });
        return;
      }
      const memberData = memberNode.data as unknown as WorkflowStepNodeData;
      const refType = memberData.step_type ?? 'platform';
      if (refType === 'parallel_group') {
        errors.push({
          nodeId: node.id,
          type: 'error',
          message: `parallel_steps ne peut pas contenir de parallel_group imbriqué ("${memberId}")`,
        });
      }
      if (refType === 'gate') {
        errors.push({
          nodeId: node.id,
          type: 'error',
          message: `parallel_steps ne peut pas contenir de step gate ("${memberId}")`,
        });
      }
    });

    const onAllSuccess = data.on_all_success_step_id;
    const onAnyError = data.on_any_error_step_id;
    for (const target of [onAllSuccess, onAnyError]) {
      if (!target || target === END_NODE_ID) continue;
      if (!nodeIds.has(target)) {
        errors.push({
          nodeId: node.id,
          type: 'error',
          message: `Cible de routing inexistante : "${target}"`,
        });
      } else if (ps.includes(target)) {
        errors.push({
          nodeId: node.id,
          type: 'error',
          message: `on_all_success_step_id / on_any_error_step_id ne peut pas cibler un membre du groupe ("${target}")`,
        });
      }
    }
  });

  return {
    valid: errors.filter((e) => e.type === 'error').length === 0,
    errors,
  };
}

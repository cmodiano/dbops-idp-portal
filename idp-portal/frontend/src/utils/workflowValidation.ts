/**
 * Workflow Validation Utilities — Story 26.5 AC2
 *
 * Extracted from WorkflowBuilderCanvas.tsx to separate concerns.
 * Validates workflow graph structure: nodes, edges, reachability, loops.
 */
import type { Node, Edge } from '@xyflow/react';
import { START_NODE_ID, END_NODE_ID } from './workflowConversion';

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
 * Validate workflow graph structure.
 *
 * Checks:
 * 1. At least one workflow node exists
 * 2. Every node has at least one output connection
 * 3. All nodes are reachable from start (no orphans)
 * 4. No infinite loops (cycle detection DFS)
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

  return {
    valid: errors.filter((e) => e.type === 'error').length === 0,
    errors,
  };
}

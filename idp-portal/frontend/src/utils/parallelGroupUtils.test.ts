import { describe, it, expect } from 'vitest';
import {
  findExecutionStepsForParallelGroup,
  computeParallelGroupStatus,
  buildParallelGroupMap,
  getStepNamesInParallelGroups,
} from './parallelGroupUtils';
import type { WorkflowStep } from '../types/api/catalog';
import type { ExecutionStepResponse } from '../types/api/executions';

const workflowSteps: WorkflowStep[] = [
  {
    order: 0,
    name: 'Backups',
    step_id: 'pg-1',
    step_type: 'parallel_group',
    parallel_steps: ['bk-db', 'bk-cfg'],
  },
  {
    order: 1,
    name: 'Backup DB',
    step_id: 'bk-db',
    step_type: 'platform',
  },
  {
    order: 2,
    name: 'Backup Config',
    step_id: 'bk-cfg',
    step_type: 'platform',
  },
  {
    order: 3,
    name: 'Apply Patch',
    step_id: 'patch',
    step_type: 'platform',
  },
];

const makeStep = (overrides: Partial<ExecutionStepResponse>): ExecutionStepResponse => ({
  id: 1,
  execution_id: 100,
  step_name: 'Step',
  step_type: 'platform',
  status: 'PENDING',
  step_order: 1,
  started_at: null,
  completed_at: null,
  error_message: null,
  output: null,
  platform_job_id: null,
  ...overrides,
});

const executionSteps: ExecutionStepResponse[] = [
  makeStep({ id: 1, step_name: 'Backup DB', status: 'COMPLETED', step_order: 1 }),
  makeStep({ id: 2, step_name: 'Backup Config', status: 'RUNNING', step_order: 2 }),
  makeStep({ id: 3, step_name: 'Apply Patch', status: 'PENDING', step_order: 3 }),
];

// ─── findExecutionStepsForParallelGroup ───────────────────────────────────────

describe('findExecutionStepsForParallelGroup', () => {
  it('retourne les sous-steps correspondant au groupe', () => {
    const result = findExecutionStepsForParallelGroup(workflowSteps[0], workflowSteps, executionSteps);
    expect(result).toHaveLength(2);
    expect(result.map((s) => s.step_name)).toEqual(['Backup DB', 'Backup Config']);
  });

  it('retourne [] si parallel_steps est vide', () => {
    const step: WorkflowStep = { ...workflowSteps[0], parallel_steps: [] };
    expect(findExecutionStepsForParallelGroup(step, workflowSteps, executionSteps)).toHaveLength(0);
  });

  it('retourne [] si parallel_steps est absent', () => {
    const step: WorkflowStep = { ...workflowSteps[0], parallel_steps: undefined };
    expect(findExecutionStepsForParallelGroup(step, workflowSteps, executionSteps)).toHaveLength(0);
  });

  it('ignore les step_id non résolus dans workflowSteps', () => {
    const step: WorkflowStep = { ...workflowSteps[0], parallel_steps: ['bk-db', 'unknown-id'] };
    const result = findExecutionStepsForParallelGroup(step, workflowSteps, executionSteps);
    expect(result).toHaveLength(1);
    expect(result[0].step_name).toBe('Backup DB');
  });
});

// ─── computeParallelGroupStatus ───────────────────────────────────────────────

describe('computeParallelGroupStatus', () => {
  it('retourne PENDING si aucun sous-step', () => {
    expect(computeParallelGroupStatus([])).toBe('PENDING');
  });

  it('retourne RUNNING si ≥1 sous-step RUNNING (sans FAILED)', () => {
    expect(
      computeParallelGroupStatus([
        makeStep({ status: 'COMPLETED' }),
        makeStep({ status: 'RUNNING' }),
      ]),
    ).toBe('RUNNING');
  });

  it('retourne FAILED si ≥1 sous-step FAILED (priorité sur RUNNING)', () => {
    expect(
      computeParallelGroupStatus([
        makeStep({ status: 'FAILED' }),
        makeStep({ status: 'RUNNING' }),
      ]),
    ).toBe('FAILED');
  });

  it('retourne FAILED si ≥1 sous-step FAILED même si les autres sont COMPLETED', () => {
    expect(
      computeParallelGroupStatus([
        makeStep({ status: 'COMPLETED' }),
        makeStep({ status: 'FAILED' }),
      ]),
    ).toBe('FAILED');
  });

  it('retourne COMPLETED si tous COMPLETED', () => {
    expect(
      computeParallelGroupStatus([
        makeStep({ status: 'COMPLETED' }),
        makeStep({ status: 'COMPLETED' }),
      ]),
    ).toBe('COMPLETED');
  });

  it('retourne SKIPPED si tous SKIPPED', () => {
    expect(
      computeParallelGroupStatus([
        makeStep({ status: 'SKIPPED' }),
        makeStep({ status: 'SKIPPED' }),
      ]),
    ).toBe('SKIPPED');
  });

  it('retourne PENDING si mix COMPLETED + PENDING (groupe pas encore fini)', () => {
    expect(
      computeParallelGroupStatus([
        makeStep({ status: 'COMPLETED' }),
        makeStep({ status: 'PENDING' }),
      ]),
    ).toBe('PENDING');
  });
});

// ─── buildParallelGroupMap ────────────────────────────────────────────────────

describe('buildParallelGroupMap', () => {
  it('construit une map avec les parallel_group et leurs sous-steps', () => {
    const map = buildParallelGroupMap(workflowSteps, executionSteps);
    expect(map.size).toBe(1);
    expect(map.has('pg-1')).toBe(true);
    const entry = map.get('pg-1')!;
    expect(entry.groupStep.name).toBe('Backups');
    expect(entry.subSteps).toHaveLength(2);
  });

  it('retourne une map vide si aucun parallel_group', () => {
    const steps: WorkflowStep[] = [workflowSteps[1], workflowSteps[2]];
    const map = buildParallelGroupMap(steps, executionSteps);
    expect(map.size).toBe(0);
  });

  it('ignore les étapes sans step_id', () => {
    const steps: WorkflowStep[] = [
      { order: 0, name: 'Groupe sans ID', step_type: 'parallel_group', parallel_steps: ['bk-db'] },
    ];
    const map = buildParallelGroupMap(steps, executionSteps);
    expect(map.size).toBe(0);
  });
});

// ─── getStepNamesInParallelGroups ─────────────────────────────────────────────

describe('getStepNamesInParallelGroups', () => {
  it('retourne les noms des sous-steps de tous les groupes', () => {
    const names = getStepNamesInParallelGroups(workflowSteps);
    expect(names.has('Backup DB')).toBe(true);
    expect(names.has('Backup Config')).toBe(true);
    expect(names.has('Apply Patch')).toBe(false);
    expect(names.has('Backups')).toBe(false);
  });

  it('retourne un Set vide si aucun parallel_group', () => {
    const steps: WorkflowStep[] = [workflowSteps[1], workflowSteps[2]];
    const names = getStepNamesInParallelGroups(steps);
    expect(names.size).toBe(0);
  });

  it('ignore les sous-steps dont le step_id ne résout pas de nom', () => {
    const steps: WorkflowStep[] = [
      { ...workflowSteps[0], parallel_steps: ['bk-db', 'nonexistent'] },
      workflowSteps[1],
    ];
    const ids = getStepNamesInParallelGroups(steps);
    expect(ids.has('Backup DB')).toBe(true);
    expect(ids.has('bk-db')).toBe(true);
    expect(ids.has('nonexistent')).toBe(false);
    expect(ids.size).toBe(2);
  });
});

// ─── Post-Story 67.5 — Fan-out multi-connexions (no parallel_group steps) ────
// Vérifie que les fonctions retournent des structures vides/correctes quand
// aucun step n'a step_type: 'parallel_group' (comportement post-67.5).

const fanOutWorkflowSteps: WorkflowStep[] = [
  {
    order: 0,
    name: 'Init',
    step_id: 's1',
    step_type: 'platform',
    on_success_step_ids: ['s2', 's3'],
  },
  {
    order: 1,
    name: 'Branch A',
    step_id: 's2',
    step_type: 'platform',
    on_success_step_ids: ['s4'],
  },
  {
    order: 2,
    name: 'Branch B',
    step_id: 's3',
    step_type: 'platform',
    on_success_step_ids: ['s4'],
  },
  {
    order: 3,
    name: 'Join',
    step_id: 's4',
    step_type: 'platform',
    on_success_step_ids: [],
  },
];

describe('buildParallelGroupMap — no parallel_group steps (post-67.5 fan-out)', () => {
  it('retourne une Map vide quand aucun step n\'a step_type parallel_group', () => {
    const result = buildParallelGroupMap(fanOutWorkflowSteps, []);
    expect(result.size).toBe(0);
  });

  it('retourne une Map vide pour une liste vide', () => {
    const result = buildParallelGroupMap([], []);
    expect(result.size).toBe(0);
  });
});

describe('getStepNamesInParallelGroups — no parallel_group steps (post-67.5 fan-out)', () => {
  it('retourne un Set vide quand aucun step n\'a step_type parallel_group', () => {
    const result = getStepNamesInParallelGroups(fanOutWorkflowSteps);
    expect(result.size).toBe(0);
  });

  it('retourne un Set vide pour une liste vide', () => {
    const result = getStepNamesInParallelGroups([]);
    expect(result.size).toBe(0);
  });
});

describe('computeParallelGroupStatus — cas 0 sous-steps', () => {
  it('retourne PENDING quand subSteps est vide (0 sous-steps)', () => {
    expect(computeParallelGroupStatus([])).toBe('PENDING');
  });
});

describe('findExecutionStepsForParallelGroup — no parallel_group steps (post-67.5 fan-out)', () => {
  it('retourne [] quand le step n\'a pas de parallel_steps (step platform fan-out)', () => {
    // Les steps platform dans un workflow fan-out n'ont pas de parallel_steps
    const fanOutStep = fanOutWorkflowSteps[0]; // s1 avec on_success_step_ids mais pas parallel_steps
    const fanOutExecSteps = [
      makeStep({ id: 10, step_name: 'Init', status: 'COMPLETED', step_order: 1 }),
      makeStep({ id: 11, step_name: 'Branch A', status: 'RUNNING', step_order: 2 }),
    ];
    const result = findExecutionStepsForParallelGroup(fanOutStep, fanOutWorkflowSteps, fanOutExecSteps);
    expect(result).toHaveLength(0);
  });

  it('retourne [] pour une liste vide de workflowSteps et executionSteps', () => {
    const fanOutStep = fanOutWorkflowSteps[0];
    const result = findExecutionStepsForParallelGroup(fanOutStep, [], []);
    expect(result).toHaveLength(0);
  });
});

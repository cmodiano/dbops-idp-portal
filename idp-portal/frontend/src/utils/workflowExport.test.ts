/**
 * Tests for workflow export/import utilities (Story 16.8).
 */

import { describe, it, expect } from 'vitest';
import yaml from 'js-yaml';
import type { WorkflowStep } from '../types/api';
import {
  sanitizeFilename,
  formatDateForFilename,
  buildWorkflowExport,
  validateWorkflowImport,
  parseWorkflowFile,
  type WorkflowExport,
  type WorkflowMetadata,
} from './workflowExport';

// ── Test fixtures ──────────────────────────────────────────────────────────

const sampleSteps: WorkflowStep[] = [
  {
    order: 1,
    step_id: 'step-aaa',
    referenced_action_id: 42,
    name: 'Backup base',
    on_success_step_id: 'step-bbb',
    on_error_step_id: 'step-ccc',
    retry_enabled: true,
    retry_max_attempts: 3,
    retry_interval_seconds: 60,
    retry_backoff_multiplier: 2.0,
  },
  {
    order: 2,
    step_id: 'step-bbb',
    referenced_action_id: 43,
    name: 'Appliquer patch',
    on_success_step_id: null,
    on_error_step_id: 'step-ccc',
    retry_enabled: false,
    retry_max_attempts: null,
    retry_interval_seconds: null,
    retry_backoff_multiplier: null,
  },
  {
    order: 3,
    step_id: 'step-ccc',
    referenced_action_id: 44,
    name: 'Rollback',
    on_success_step_id: null,
    on_error_step_id: null,
    retry_enabled: false,
    retry_max_attempts: null,
    retry_interval_seconds: null,
    retry_backoff_multiplier: null,
  },
];

const sampleMetadata: WorkflowMetadata = {
  name: 'Patching Oracle Production',
  description: 'Workflow de patching avec validation et rollback',
  tags: ['oracle', 'production', 'patching'],
};

function buildValidExport(): WorkflowExport {
  return buildWorkflowExport(sampleSteps, sampleMetadata);
}

// ── sanitizeFilename ───────────────────────────────────────────────────────

describe('sanitizeFilename', () => {
  it('replaces forbidden characters with underscore', () => {
    expect(sanitizeFilename('file/name:test*?"<>|end')).toBe('file_name_test_end');
  });

  it('replaces spaces with underscores', () => {
    expect(sanitizeFilename('My Workflow Name')).toBe('My_Workflow_Name');
  });

  it('collapses multiple underscores', () => {
    expect(sanitizeFilename('a///b:::c')).toBe('a_b_c');
  });

  it('trims leading and trailing underscores', () => {
    expect(sanitizeFilename('/hello/')).toBe('hello');
  });

  it('returns "workflow" for empty string', () => {
    expect(sanitizeFilename('')).toBe('workflow');
  });

  it('truncates to 100 characters', () => {
    const longName = 'a'.repeat(150);
    expect(sanitizeFilename(longName).length).toBeLessThanOrEqual(100);
  });
});

// ── formatDateForFilename ──────────────────────────────────────────────────

describe('formatDateForFilename', () => {
  it('formats date as YYYY-MM-DD_HH-mm-ss', () => {
    const date = new Date(2026, 1, 6, 14, 30, 5); // Feb 6 2026, 14:30:05
    expect(formatDateForFilename(date)).toBe('2026-02-06_14-30-05');
  });

  it('pads single-digit values', () => {
    const date = new Date(2026, 0, 1, 1, 2, 3); // Jan 1 2026, 01:02:03
    expect(formatDateForFilename(date)).toBe('2026-01-01_01-02-03');
  });
});

// ── buildWorkflowExport ────────────────────────────────────────────────────

describe('buildWorkflowExport', () => {
  it('creates a valid export structure with version 1.0', () => {
    const result = buildValidExport();
    expect(result.version).toBe('1.0');
    expect(result.workflow.name).toBe('Patching Oracle Production');
    expect(result.workflow.description).toBe('Workflow de patching avec validation et rollback');
    expect(result.workflow.tags).toEqual(['oracle', 'production', 'patching']);
    expect(result.workflow.steps).toHaveLength(3);
  });

  it('preserves step data correctly', () => {
    const result = buildValidExport();
    const step1 = result.workflow.steps[0];
    expect(step1.step_id).toBe('step-aaa');
    expect(step1.referenced_action_id).toBe(42);
    expect(step1.name).toBe('Backup base');
    expect(step1.on_success_step_id).toBe('step-bbb');
    expect(step1.on_error_step_id).toBe('step-ccc');
    expect(step1.retry_enabled).toBe(true);
    expect(step1.retry_max_attempts).toBe(3);
    expect(step1.retry_interval_seconds).toBe(60);
    expect(step1.retry_backoff_multiplier).toBe(2.0);
  });

  it('handles null metadata gracefully', () => {
    const result = buildWorkflowExport(sampleSteps, { name: 'Test', description: null, tags: [] });
    expect(result.workflow.description).toBeNull();
    expect(result.workflow.tags).toEqual([]);
  });
});

// ── validateWorkflowImport ─────────────────────────────────────────────────

describe('validateWorkflowImport', () => {
  it('accepts a valid export', () => {
    const errors = validateWorkflowImport(buildValidExport());
    expect(errors).toEqual([]);
  });

  it('rejects non-object input', () => {
    expect(validateWorkflowImport('string')).toContain('Le fichier ne contient pas un objet valide.');
    expect(validateWorkflowImport(null)).toContain('Le fichier ne contient pas un objet valide.');
    expect(validateWorkflowImport(42)).toContain('Le fichier ne contient pas un objet valide.');
  });

  it('rejects missing version', () => {
    const data = { workflow: { name: 'Test', steps: [{ step_id: 'a', referenced_action_id: 1, name: 'X' }] } };
    const errors = validateWorkflowImport(data);
    expect(errors.some((e) => e.includes('Version'))).toBe(true);
  });

  it('rejects wrong version', () => {
    const data = { version: '2.0', workflow: { name: 'Test', steps: [{ step_id: 'a', referenced_action_id: 1, name: 'X' }] } };
    const errors = validateWorkflowImport(data);
    expect(errors.some((e) => e.includes('Version'))).toBe(true);
  });

  it('rejects missing workflow', () => {
    const errors = validateWorkflowImport({ version: '1.0' });
    expect(errors.some((e) => e.includes('workflow'))).toBe(true);
  });

  it('rejects missing name', () => {
    const data = { version: '1.0', workflow: { steps: [{ step_id: 'a', referenced_action_id: 1 }] } };
    const errors = validateWorkflowImport(data);
    expect(errors.some((e) => e.includes('nom du workflow'))).toBe(true);
  });

  it('rejects empty steps array', () => {
    const data = { version: '1.0', workflow: { name: 'Test', steps: [] } };
    const errors = validateWorkflowImport(data);
    expect(errors.some((e) => e.includes('Au moins une étape'))).toBe(true);
  });

  it('rejects missing step_id', () => {
    const data = { version: '1.0', workflow: { name: 'Test', steps: [{ referenced_action_id: 1 }] } };
    const errors = validateWorkflowImport(data);
    expect(errors.some((e) => e.includes('step_id'))).toBe(true);
  });

  it('rejects invalid referenced_action_id', () => {
    const data = { version: '1.0', workflow: { name: 'Test', steps: [{ step_id: 'a', referenced_action_id: -1 }] } };
    const errors = validateWorkflowImport(data);
    expect(errors.some((e) => e.includes('referenced_action_id'))).toBe(true);
  });

  it('rejects duplicate step_id', () => {
    const data = {
      version: '1.0',
      workflow: {
        name: 'Test',
        steps: [
          { step_id: 'same', referenced_action_id: 1, name: 'A' },
          { step_id: 'same', referenced_action_id: 2, name: 'B' },
        ],
      },
    };
    const errors = validateWorkflowImport(data);
    expect(errors.some((e) => e.includes('doublon'))).toBe(true);
  });

  it('rejects invalid on_success_step_id reference', () => {
    const data = {
      version: '1.0',
      workflow: {
        name: 'Test',
        steps: [
          { step_id: 'a', referenced_action_id: 1, name: 'A', on_success_step_id: 'nonexistent' },
        ],
      },
    };
    const errors = validateWorkflowImport(data);
    expect(errors.some((e) => e.includes('inexistant'))).toBe(true);
  });

  it('rejects self-referencing on_success_step_id', () => {
    const data = {
      version: '1.0',
      workflow: {
        name: 'Test',
        steps: [
          { step_id: 'a', referenced_action_id: 1, name: 'A', on_success_step_id: 'a' },
        ],
      },
    };
    const errors = validateWorkflowImport(data);
    expect(errors.some((e) => e.includes('auto-référence'))).toBe(true);
  });

  it('rejects self-referencing on_error_step_id', () => {
    const data = {
      version: '1.0',
      workflow: {
        name: 'Test',
        steps: [
          { step_id: 'a', referenced_action_id: 1, name: 'A', on_error_step_id: 'a' },
        ],
      },
    };
    const errors = validateWorkflowImport(data);
    expect(errors.some((e) => e.includes('auto-référence'))).toBe(true);
  });

  it('rejects retry enabled without max_attempts', () => {
    const data = {
      version: '1.0',
      workflow: {
        name: 'Test',
        steps: [
          { step_id: 'a', referenced_action_id: 1, name: 'A', retry_enabled: true },
        ],
      },
    };
    const errors = validateWorkflowImport(data);
    expect(errors.some((e) => e.includes('retry_max_attempts'))).toBe(true);
  });

  it('accepts valid inter-step references', () => {
    const data = {
      version: '1.0',
      workflow: {
        name: 'Test',
        steps: [
          { step_id: 'a', referenced_action_id: 1, name: 'A', on_success_step_id: 'b' },
          { step_id: 'b', referenced_action_id: 2, name: 'B', on_error_step_id: 'a' },
        ],
      },
    };
    const errors = validateWorkflowImport(data);
    expect(errors).toEqual([]);
  });

  it('rejects more than 100 steps', () => {
    const steps = Array.from({ length: 101 }, (_, i) => ({
      step_id: `step-${i}`,
      referenced_action_id: i + 1,
      name: `Step ${i}`,
    }));
    const data = { version: '1.0', workflow: { name: 'Test', steps } };
    const errors = validateWorkflowImport(data);
    expect(errors.some((e) => e.includes('100'))).toBe(true);
  });

  it('accepts retry_backoff_multiplier exactly 1.0 (minimum boundary)', () => {
    const data = {
      version: '1.0',
      workflow: {
        name: 'Test',
        steps: [{
          step_id: 'a',
          referenced_action_id: 1,
          name: 'Step',
          retry_enabled: true,
          retry_max_attempts: 1,
          retry_interval_seconds: 1,
          retry_backoff_multiplier: 1.0, // Minimum valid value
        }],
      },
    };
    const errors = validateWorkflowImport(data);
    expect(errors).toEqual([]);
  });

  it('accepts empty tags array', () => {
    const data = {
      version: '1.0',
      workflow: {
        name: 'Test',
        tags: [], // Empty is valid
        steps: [{ step_id: 'a', referenced_action_id: 1, name: 'Step' }],
      },
    };
    const errors = validateWorkflowImport(data);
    expect(errors).toEqual([]);
  });

  it('accepts null description and null name for steps', () => {
    const data = {
      version: '1.0',
      workflow: {
        name: 'Test',
        description: null, // Null is valid
        steps: [{
          step_id: 'a',
          referenced_action_id: 1,
          name: null, // Null is valid for step name
        }],
      },
    };
    const errors = validateWorkflowImport(data);
    expect(errors).toEqual([]);
  });
});

// ── parseWorkflowFile (JSON) ───────────────────────────────────────────────

describe('parseWorkflowFile (JSON)', () => {
  it('parses valid JSON successfully', () => {
    const json = JSON.stringify(buildValidExport());
    const result = parseWorkflowFile(json, '.json');
    expect(result.valid).toBe(true);
    expect(result.data).not.toBeNull();
    expect(result.data!.workflow.name).toBe('Patching Oracle Production');
    expect(result.data!.workflow.steps).toHaveLength(3);
    expect(result.errors).toEqual([]);
  });

  it('returns error for malformed JSON', () => {
    const result = parseWorkflowFile('{ invalid json', '.json');
    expect(result.valid).toBe(false);
    expect(result.data).toBeNull();
    expect(result.errors[0]).toContain('Erreur de parsing');
  });

  it('returns validation errors for valid JSON but invalid structure', () => {
    const result = parseWorkflowFile('{"version":"2.0"}', '.json');
    expect(result.valid).toBe(false);
    expect(result.errors.length).toBeGreaterThan(0);
  });

  it('preserves retry config through round-trip', () => {
    const json = JSON.stringify(buildValidExport());
    const result = parseWorkflowFile(json, '.json');
    const step1 = result.data!.workflow.steps[0];
    expect(step1.retry_enabled).toBe(true);
    expect(step1.retry_max_attempts).toBe(3);
    expect(step1.retry_interval_seconds).toBe(60);
    expect(step1.retry_backoff_multiplier).toBe(2.0);
  });

  it('normalizes missing optional fields', () => {
    const data = {
      version: '1.0',
      workflow: {
        name: 'Test',
        steps: [{ step_id: 'a', referenced_action_id: 1 }],
      },
    };
    const result = parseWorkflowFile(JSON.stringify(data), '.json');
    expect(result.valid).toBe(true);
    const step = result.data!.workflow.steps[0];
    expect(step.name).toBeNull();
    expect(step.on_success_step_id).toBeNull();
    expect(step.on_error_step_id).toBeNull();
    expect(step.retry_enabled).toBe(false);
    expect(step.retry_max_attempts).toBeNull();
  });
});

// ── parseWorkflowFile (YAML) ───────────────────────────────────────────────

describe('parseWorkflowFile (YAML)', () => {
  it('parses valid YAML successfully', () => {
    const yamlContent = `version: '1.0'
workflow:
  name: Test Workflow
  description: A test
  tags:
    - tag1
    - tag2
  steps:
    - step_id: step-1
      referenced_action_id: 10
      name: Step One
      on_success_step_id: step-2
      on_error_step_id: null
      retry_enabled: false
    - step_id: step-2
      referenced_action_id: 20
      name: Step Two
      retry_enabled: true
      retry_max_attempts: 5
      retry_interval_seconds: 30
      retry_backoff_multiplier: 1.5
`;
    const result = parseWorkflowFile(yamlContent, '.yaml');
    expect(result.valid).toBe(true);
    expect(result.data!.workflow.name).toBe('Test Workflow');
    expect(result.data!.workflow.steps).toHaveLength(2);
  });

  it('supports .yml extension', () => {
    const yamlContent = `version: '1.0'\nworkflow:\n  name: Test\n  steps:\n    - step_id: a\n      referenced_action_id: 1\n      name: A`;
    const result = parseWorkflowFile(yamlContent, '.yml');
    expect(result.valid).toBe(true);
  });

  it('returns error for malformed YAML', () => {
    const result = parseWorkflowFile('{ invalid: yaml: bad:', '.yaml');
    expect(result.valid).toBe(false);
    expect(result.errors[0]).toContain('Erreur de parsing');
  });

  it('rejects unsupported extension', () => {
    const result = parseWorkflowFile('content', '.txt');
    expect(result.valid).toBe(false);
    expect(result.errors[0]).toContain('Extension');
  });
});

// ── Round-trip JSON ↔ YAML ─────────────────────────────────────────────────

describe('Round-trip JSON ↔ YAML', () => {
  it('exports JSON → import → same data', () => {
    const exportObj = buildValidExport();
    const json = JSON.stringify(exportObj);
    const result = parseWorkflowFile(json, '.json');
    expect(result.valid).toBe(true);
    expect(result.data!.workflow.steps).toHaveLength(exportObj.workflow.steps.length);
    expect(result.data!.workflow.name).toBe(exportObj.workflow.name);
  });

  it('export YAML → import → same data structure', async () => {
    // Simulate YAML export by using js-yaml
    const exportObj = buildValidExport();
    const yamlString = yaml.dump(exportObj);
    const result = parseWorkflowFile(yamlString, '.yaml');
    expect(result.valid).toBe(true);
    expect(result.data!.workflow.steps).toHaveLength(exportObj.workflow.steps.length);
    expect(result.data!.workflow.name).toBe(exportObj.workflow.name);
  });
});

// ── Story 65.4 — parallel_group ────────────────────────────────────────────

describe('buildWorkflowExport — parallel_group (AC #4)', () => {
  it('inclut step_type, parallel_steps, on_all_success_step_id pour parallel_group', () => {
    const steps: WorkflowStep[] = [
      {
        order: 1, step_id: 'pg-1', step_type: 'parallel_group', name: 'PG',
        parallel_steps: ['s1', 's2'], on_all_success_step_id: 's3', on_any_error_step_id: null,
      },
    ];
    const result = buildWorkflowExport(steps, { name: 'Test', description: null, tags: [] });
    const exported = result.workflow.steps[0];

    expect(exported.step_type).toBe('parallel_group');
    expect((exported as unknown as Record<string, unknown>).parallel_steps).toEqual(['s1', 's2']);
    expect((exported as unknown as Record<string, unknown>).on_all_success_step_id).toBe('s3');
    expect((exported as unknown as Record<string, unknown>).on_any_error_step_id).toBeNull();
    expect((exported as unknown as Record<string, unknown>).referenced_action_id).toBeUndefined();
    expect((exported as unknown as Record<string, unknown>).retry_enabled).toBeUndefined();
  });

  it('inclut step_type pour les steps non-parallel_group', () => {
    const steps: WorkflowStep[] = [
      { order: 1, step_id: 'step-1', step_type: 'platform', name: 'Test', referenced_action_id: 42 },
    ];
    const result = buildWorkflowExport(steps, { name: 'W', description: null, tags: [] });
    expect(result.workflow.steps[0].step_type).toBe('platform');
  });
});

describe('validateWorkflowImport — parallel_group (AC #5)', () => {
  const makeParallelGroupImport = (parallel_steps: unknown) => ({
    version: '1.0',
    workflow: {
      name: 'Test',
      description: null,
      tags: [],
      steps: [
        { step_id: 'pg-1', step_type: 'parallel_group', name: 'PG',
          parallel_steps, on_all_success_step_id: null, on_any_error_step_id: null },
        { step_id: 's1', step_type: 'platform', name: 'S1', referenced_action_id: 1 },
        { step_id: 's2', step_type: 'platform', name: 'S2', referenced_action_id: 2 },
      ],
    },
  });

  it('accepte un parallel_group valide avec parallel_steps ≥ 2', () => {
    const errors = validateWorkflowImport(makeParallelGroupImport(['s1', 's2']));
    expect(errors).toHaveLength(0);
  });

  it('rejette parallel_group avec parallel_steps < 2 (1 élément)', () => {
    const errors = validateWorkflowImport(makeParallelGroupImport(['s1']));
    expect(errors.length).toBeGreaterThan(0);
    expect(errors.some((e) => e.includes('parallel_steps'))).toBe(true);
  });

  it('rejette parallel_group avec parallel_steps absent', () => {
    const errors = validateWorkflowImport(makeParallelGroupImport(undefined));
    expect(errors.length).toBeGreaterThan(0);
    expect(errors.some((e) => e.includes('parallel_steps'))).toBe(true);
  });

  it('rejette parallel_group avec parallel_steps vide', () => {
    const errors = validateWorkflowImport(makeParallelGroupImport([]));
    expect(errors.length).toBeGreaterThan(0);
    expect(errors.some((e) => e.includes('parallel_steps'))).toBe(true);
  });

  it('rejette parallel_group dont parallel_steps référence un step_id inexistant', () => {
    const data = {
      version: '1.0',
      workflow: {
        name: 'Test', description: null, tags: [],
        steps: [
          { step_id: 'pg-1', step_type: 'parallel_group', name: 'PG',
            parallel_steps: ['s1', 'inexistant'], on_all_success_step_id: null, on_any_error_step_id: null },
          { step_id: 's1', step_type: 'platform', name: 'S1', referenced_action_id: 1 },
        ],
      },
    };
    const errors = validateWorkflowImport(data);
    expect(errors.some((e) => e.includes('inexistant'))).toBe(true);
  });

  it('rejette parallel_group avec parallel_steps contenant des doublons', () => {
    const errors = validateWorkflowImport(makeParallelGroupImport(['s1', 's1']));
    expect(errors.length).toBeGreaterThan(0);
    expect(errors.some((e) => e.includes('dupliqués'))).toBe(true);
  });

  it('rejette parallel_group dont parallel_steps contient son propre step_id (auto-référence)', () => {
    const data = {
      version: '1.0',
      workflow: {
        name: 'Test', description: null, tags: [],
        steps: [
          { step_id: 'pg-1', step_type: 'parallel_group', name: 'PG',
            parallel_steps: ['pg-1', 's1'], on_all_success_step_id: null, on_any_error_step_id: null },
          { step_id: 's1', step_type: 'platform', name: 'S1', referenced_action_id: 1 },
        ],
      },
    };
    const errors = validateWorkflowImport(data);
    expect(errors.some((e) => e.includes('auto-référence'))).toBe(true);
  });

  it('rejette parallel_group avec on_all_success_step_id auto-référencé', () => {
    const data = {
      version: '1.0',
      workflow: {
        name: 'Test', description: null, tags: [],
        steps: [
          { step_id: 'pg-1', step_type: 'parallel_group', name: 'PG',
            parallel_steps: ['s1', 's2'], on_all_success_step_id: 'pg-1', on_any_error_step_id: null },
          { step_id: 's1', step_type: 'platform', name: 'S1', referenced_action_id: 1 },
          { step_id: 's2', step_type: 'platform', name: 'S2', referenced_action_id: 2 },
        ],
      },
    };
    const errors = validateWorkflowImport(data);
    expect(errors.some((e) => e.includes('auto-référence'))).toBe(true);
  });

  it('rejette parallel_group avec on_any_error_step_id auto-référencé', () => {
    const data = {
      version: '1.0',
      workflow: {
        name: 'Test', description: null, tags: [],
        steps: [
          { step_id: 'pg-1', step_type: 'parallel_group', name: 'PG',
            parallel_steps: ['s1', 's2'], on_all_success_step_id: null, on_any_error_step_id: 'pg-1' },
          { step_id: 's1', step_type: 'platform', name: 'S1', referenced_action_id: 1 },
          { step_id: 's2', step_type: 'platform', name: 'S2', referenced_action_id: 2 },
        ],
      },
    };
    const errors = validateWorkflowImport(data);
    expect(errors.some((e) => e.includes('auto-référence'))).toBe(true);
  });
});

describe('parseWorkflowFile — parallel_group (AC #6)', () => {
  it('normalise correctement les steps parallel_group depuis JSON', () => {
    const data = {
      version: '1.0',
      workflow: {
        name: 'Test', description: null, tags: [],
        steps: [
          { step_id: 'pg-1', step_type: 'parallel_group', name: 'PG',
            parallel_steps: ['s1', 's2'], on_all_success_step_id: null, on_any_error_step_id: null, order: 1 },
          { step_id: 's1', step_type: 'platform', name: 'S1', referenced_action_id: 1, order: 2 },
          { step_id: 's2', step_type: 'platform', name: 'S2', referenced_action_id: 2, order: 3 },
        ],
      },
    };
    const result = parseWorkflowFile(JSON.stringify(data), '.json');
    expect(result.valid).toBe(true);

    const pgStep = result.data!.workflow.steps.find((s) => s.step_id === 'pg-1');
    expect(pgStep?.step_type).toBe('parallel_group');
    expect(pgStep?.parallel_steps).toEqual(['s1', 's2']);
    expect(pgStep?.on_all_success_step_id).toBeNull();
    expect(pgStep?.on_any_error_step_id).toBeNull();
    expect((pgStep as unknown as Record<string, unknown>).referenced_action_id).toBeUndefined();
    expect((pgStep as unknown as Record<string, unknown>).retry_enabled).toBeUndefined();
  });

  it('normalise correctement les steps parallel_group depuis YAML', () => {
    const yamlContent = `version: '1.0'
workflow:
  name: Test
  description: null
  tags: []
  steps:
    - step_id: pg-1
      step_type: parallel_group
      name: PG
      parallel_steps:
        - s1
        - s2
      on_all_success_step_id: s2
      on_any_error_step_id: null
      order: 1
    - step_id: s1
      step_type: platform
      name: S1
      referenced_action_id: 1
      order: 2
    - step_id: s2
      step_type: platform
      name: S2
      referenced_action_id: 2
      order: 3
`;
    const result = parseWorkflowFile(yamlContent, '.yaml');
    expect(result.valid).toBe(true);

    const pgStep = result.data!.workflow.steps.find((s) => s.step_id === 'pg-1');
    expect(pgStep?.step_type).toBe('parallel_group');
    expect(pgStep?.parallel_steps).toEqual(['s1', 's2']);
    expect(pgStep?.on_all_success_step_id).toBe('s2');
    expect(pgStep?.on_any_error_step_id).toBeNull();
    expect((pgStep as unknown as Record<string, unknown>).referenced_action_id).toBeUndefined();
  });
});

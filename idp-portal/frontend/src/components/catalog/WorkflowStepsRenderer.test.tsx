/**
 * Tests for WorkflowStepsRenderer component (Story 20.4, Task 2.3).
 *
 * Tests:
 * - Rendering workflow steps with action names
 * - Loading state display
 * - Error state display
 * - Validation error summary display
 * - Steps with no parameters show info alert
 *
 * Story 62.1 additions:
 * - extractCommonParameters unit tests
 * - Common parameters section (visible / hidden)
 * - Common fields excluded from per-step blocks
 * - Inventory field rendering in common section
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { Form, App } from 'antd';
import { WorkflowStepsRenderer, extractCommonParameters } from './WorkflowStepsRenderer';
import { extractParameterFields } from '../../hooks/useDynamicForm';
import type { ParameterField } from '../../hooks/useDynamicForm';
import type { CatalogActionDetail } from '../../services/catalog_service';
import { renderFieldInput } from './renderFieldInput';

vi.mock('./renderFieldInput', () => ({
  renderFieldInput: vi.fn((_field: ParameterField) => <div data-testid="field-input" />),
}));

// Minimal mock for useDynamicForm
vi.mock('../../hooks/useDynamicForm', () => ({
  extractParameterFields: vi.fn().mockImplementation((schema: Record<string, unknown> | null) => {
    if (!schema || !schema.properties) return [];
    const props = schema.properties as Record<string, Record<string, unknown>>;
    return Object.entries(props).map(([name, prop]) => ({
      name,
      label: (prop.title as string) || name,
      type: (prop.type as string) || 'string',
      required: false,
      description: prop.description || null,
      inventorySource: prop.inventorySource || undefined,
      inventoryValueColumn: prop.inventoryValueColumn || undefined,
    }));
  }),
}));


const mockWorkflowSteps = [
  { order: 1, name: 'Stop DB', referenced_action_id: 101 },
  { order: 2, name: 'Patch', referenced_action_id: 102 },
];

const mockStepActions: Record<number, CatalogActionDetail> = {
  101: {
    id: 101,
    name: 'Stop Database',
    parameters_schema: { properties: { db_name: { title: 'Database Name', type: 'string' } } },
  } as unknown as CatalogActionDetail,
  102: {
    id: 102,
    name: 'Apply Patch',
    parameters_schema: null,
  } as unknown as CatalogActionDetail,
};

function renderComponent(overrides = {}) {
  const defaultProps = {
    workflowSteps: mockWorkflowSteps,
    workflowStepActions: mockStepActions,
    loadingWorkflowStepActions: false,
    workflowStepActionsError: null,
    workflowValidationSummary: null,
    variant: 'default' as const,
    inventoryData: {},
    inventoryWarnings: {},
    loadingInventory: false,
    ...overrides,
  };

  return render(
    <App>
      <FormWrapper {...defaultProps} />
    </App>
  );
}

// Form wrapper that creates real form instance
function FormWrapper(props: Parameters<typeof WorkflowStepsRenderer>[0] & { form?: unknown }) {
  const [form] = Form.useForm();
  return (
    <Form form={form}>
      <WorkflowStepsRenderer {...props} />
    </Form>
  );
}

describe('WorkflowStepsRenderer', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders workflow steps with action names', () => {
    renderComponent();

    expect(screen.getByText(/Étape 1 — Stop Database/)).toBeInTheDocument();
    expect(screen.getByText(/Étape 2 — Apply Patch/)).toBeInTheDocument();
  });

  it('shows fallback action name when action not loaded', () => {
    renderComponent({
      workflowStepActions: {},
    });

    expect(screen.getByText(/Étape 1 — Action #101/)).toBeInTheDocument();
    expect(screen.getByText(/Étape 2 — Action #102/)).toBeInTheDocument();
  });

  it('shows loading state', () => {
    renderComponent({
      loadingWorkflowStepActions: true,
    });

    expect(screen.getByText('Chargement des étapes du workflow...')).toBeInTheDocument();
  });

  it('shows error state', () => {
    renderComponent({
      workflowStepActionsError: 'API error: 500',
    });

    expect(screen.getByText('Impossible de charger les actions du workflow')).toBeInTheDocument();
    expect(screen.getByText('API error: 500')).toBeInTheDocument();
  });

  it('shows validation summary when present', () => {
    renderComponent({
      workflowValidationSummary: 'Étapes invalides : 1, 2',
    });

    expect(screen.getByText('Certaines étapes sont invalides')).toBeInTheDocument();
    expect(screen.getByText('Étapes invalides : 1, 2')).toBeInTheDocument();
  });

  it('shows info alert for steps with no parameters', () => {
    renderComponent();

    // Step 2 (Apply Patch) has null parameters_schema
    expect(screen.getByText("Cette action n'a pas de paramètres")).toBeInTheDocument();
  });

  it('renders parameter fields for steps with schema', () => {
    renderComponent();

    // Step 1 (Stop Database) has db_name parameter
    expect(screen.getByText('Database Name')).toBeInTheDocument();
  });
});

// ─── Coverage extras ──────────────────────────────────────────────────────────
describe('WorkflowStepsRenderer — coverage extras', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders step with two fields using the extractParameterFields mock (covers first/non-first field branch)', () => {
    // The existing mock returns fields from schema.properties
    // Provide a schema with two properties so both first-field (ref wrapper) and non-first paths are exercised
    const stepActionsWithTwoFields: Record<number, CatalogActionDetail> = {
      101: {
        id: 101,
        name: 'Two-Field Action',
        parameters_schema: {
          properties: {
            db_name: { title: 'Database Name', type: 'string' },
            port: { title: 'Port', type: 'number' },
          },
        },
      } as unknown as CatalogActionDetail,
    };

    renderComponent({
      workflowSteps: [{ order: 1, name: 'Step 1', referenced_action_id: 101 }],
      workflowStepActions: stepActionsWithTwoFields,
    });

    // Both fields rendered: first uses ref wrapper div, second does not
    expect(screen.getByText('Database Name')).toBeInTheDocument();
    expect(screen.getByText('Port')).toBeInTheDocument();
  });

  it('covers required/pattern/minimum/maximum rule-building AND tooltip truthy branch via description', () => {
    const fields = [
      {
        name: 'count',
        label: 'Count',
        type: 'number',
        required: true,
        pattern: '^[0-9]+$',
        minimum: 1,
        maximum: 100,
        description: 'Enter a count value',
      } as ParameterField,
      {
        name: 'label',
        label: 'Label',
        type: 'string',
        required: false,
        description: 'Enter a label',
      } as ParameterField,
    ];
    // extractCommonParameters calls extractParameterFields once per step:
    //   step 101 (non-null schema) → first mockImplementationOnce
    //   step 102 (null schema)     → default mock returns []
    // Per-step rendering then calls it again:
    //   step 101 → second mockImplementationOnce
    //   step 102 (null schema) → default mock returns []
    vi.mocked(extractParameterFields)
      .mockImplementationOnce(() => fields) // extractCommonParameters: step 101
      .mockImplementationOnce(() => fields); // per-step rendering: step 101

    renderComponent({
      workflowSteps: [{ order: 1, name: 'Step 1', referenced_action_id: 101 }],
      workflowStepActions: mockStepActions,
    });

    // Both fields rendered — first (index=0) uses ref wrapper, second (index=1) uses plain Form.Item
    // description is truthy → tooltip object is created (covers tooltip truthy branches 121, 133)
    // required=true covers line 106 body; pattern covers 107; minimum covers 108; maximum covers 109
    expect(screen.getByText('Count')).toBeInTheDocument();
    expect(screen.getByText('Label')).toBeInTheDocument();
  });

  it('renders no-parameters alert for a second step when first step has parameters (covers stepIndex>0 path)', () => {
    // Step 1 has fields, step 2 has null schema → "Cette action n'a pas de paramètres"
    const stepActionsForTwoSteps: Record<number, CatalogActionDetail> = {
      201: {
        id: 201,
        name: 'Has Params',
        parameters_schema: { properties: { col: { title: 'Column', type: 'string' } } },
      } as unknown as CatalogActionDetail,
      202: {
        id: 202,
        name: 'No Params',
        parameters_schema: null,
      } as unknown as CatalogActionDetail,
    };

    renderComponent({
      workflowSteps: [
        { order: 1, name: 'Step 1', referenced_action_id: 201 },
        { order: 2, name: 'Step 2', referenced_action_id: 202 },
      ],
      workflowStepActions: stepActionsForTwoSteps,
    });

    expect(screen.getByText('Column')).toBeInTheDocument();
    expect(screen.getByText("Cette action n'a pas de paramètres")).toBeInTheDocument();
  });
});

// ─── Story 62.1: extractCommonParameters unit tests ───────────────────────────
describe('extractCommonParameters', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  // Build a minimal CatalogActionDetail stub
  function makeAction(id: number, fields: Record<string, ParameterField>): CatalogActionDetail {
    return {
      id,
      name: `Action ${id}`,
      parameters_schema: { properties: fields },
    } as unknown as CatalogActionDetail;
  }

  it('returns empty when no steps', () => {
    const result = extractCommonParameters({}, []);
    expect(result.commonFields).toHaveLength(0);
    expect(result.commonKeys.size).toBe(0);
  });

  it('returns empty when only one step', () => {
    const actions = { 1: makeAction(1, {}) };
    const steps = [{ order: 1, referenced_action_id: 1 }];
    // Mock single call
    vi.mocked(extractParameterFields).mockImplementationOnce(() => [
      { name: 'server', label: 'Server', type: 'string', required: false },
    ] as ParameterField[]);

    const result = extractCommonParameters(actions, steps);
    expect(result.commonFields).toHaveLength(0);
    expect(result.commonKeys.size).toBe(0);
  });

  it('identifies shared parameters across two steps', () => {
    const actions = {
      1: makeAction(1, {}),
      2: makeAction(2, {}),
    };
    const steps = [
      { order: 1, referenced_action_id: 1 },
      { order: 2, referenced_action_id: 2 },
    ];
    // Both steps return server_id + env; only server_id is shared (same key)
    vi.mocked(extractParameterFields)
      .mockImplementationOnce(() => [
        { name: 'server_id', label: 'Server', type: 'string', required: false },
        { name: 'specific_1', label: 'Specific 1', type: 'string', required: false },
      ] as ParameterField[])
      .mockImplementationOnce(() => [
        { name: 'server_id', label: 'Server', type: 'string', required: false },
        { name: 'specific_2', label: 'Specific 2', type: 'string', required: false },
      ] as ParameterField[]);

    const result = extractCommonParameters(actions, steps);
    expect(result.commonFields).toHaveLength(1);
    expect(result.commonFields[0].name).toBe('server_id');
    // commonKeys stores paramKey strings: "name|inventorySource|inventoryValueColumn"
    expect(result.commonKeys.has('server_id||')).toBe(true);
    expect(result.commonKeys.has('specific_1||')).toBe(false);
  });

  it('returns empty when steps share no parameters', () => {
    const actions = {
      1: makeAction(1, {}),
      2: makeAction(2, {}),
    };
    const steps = [
      { order: 1, referenced_action_id: 1 },
      { order: 2, referenced_action_id: 2 },
    ];
    vi.mocked(extractParameterFields)
      .mockImplementationOnce(() => [{ name: 'param_a', label: 'A', type: 'string', required: false }] as ParameterField[])
      .mockImplementationOnce(() => [{ name: 'param_b', label: 'B', type: 'string', required: false }] as ParameterField[]);

    const result = extractCommonParameters(actions, steps);
    expect(result.commonFields).toHaveLength(0);
    expect(result.commonKeys.size).toBe(0);
  });

  it('ignores steps with referenced_action_id == null', () => {
    const actions = { 1: makeAction(1, {}) };
    const steps = [
      { order: 1, referenced_action_id: null },
      { order: 2, referenced_action_id: 1 },
    ];
    vi.mocked(extractParameterFields).mockImplementationOnce(() => [
      { name: 'server_id', label: 'Server', type: 'string', required: false },
    ] as ParameterField[]);

    // Only one valid step → no common params
    const result = extractCommonParameters(actions, steps);
    expect(result.commonFields).toHaveLength(0);
  });

  it('ignores steps whose action is not in workflowStepActions', () => {
    const actions = { 1: makeAction(1, {}) };
    const steps = [
      { order: 1, referenced_action_id: 1 },
      { order: 2, referenced_action_id: 999 }, // 999 not in actions
    ];
    vi.mocked(extractParameterFields).mockImplementationOnce(() => [
      { name: 'server_id', label: 'Server', type: 'string', required: false },
    ] as ParameterField[]);

    const result = extractCommonParameters(actions, steps);
    // Only one valid step → no common params
    expect(result.commonFields).toHaveLength(0);
  });

  it('uses inventorySource and inventoryValueColumn in key (same name, different inventory = not common)', () => {
    const actions = {
      1: makeAction(1, {}),
      2: makeAction(2, {}),
    };
    const steps = [
      { order: 1, referenced_action_id: 1 },
      { order: 2, referenced_action_id: 2 },
    ];
    vi.mocked(extractParameterFields)
      .mockImplementationOnce(() => [
        { name: 'target', label: 'Target', type: 'string', required: false, inventorySource: 'servers' as const },
      ] as ParameterField[])
      .mockImplementationOnce(() => [
        { name: 'target', label: 'Target', type: 'string', required: false, inventorySource: 'databases' as const },
      ] as ParameterField[]);

    // Same name but different inventorySource → different keys → NOT common
    const result = extractCommonParameters(actions, steps);
    expect(result.commonFields).toHaveLength(0);
  });

  it('identifies inventory parameters as common when inventorySource matches', () => {
    const actions = {
      1: makeAction(1, {}),
      2: makeAction(2, {}),
    };
    const steps = [
      { order: 1, referenced_action_id: 1 },
      { order: 2, referenced_action_id: 2 },
    ];
    vi.mocked(extractParameterFields)
      .mockImplementationOnce(() => [
        { name: 'server_id', label: 'Server', type: 'string', required: false, inventorySource: 'servers' as const },
      ] as ParameterField[])
      .mockImplementationOnce(() => [
        { name: 'server_id', label: 'Server', type: 'string', required: false, inventorySource: 'servers' as const },
      ] as ParameterField[]);

    const result = extractCommonParameters(actions, steps);
    expect(result.commonFields).toHaveLength(1);
    expect(result.commonFields[0].inventorySource).toBe('servers');
    // paramKey for an inventory field: "server_id|servers|"
    expect(result.commonKeys.has('server_id|servers|')).toBe(true);
  });
});

// ─── Story 62.1: WorkflowStepsRenderer integration tests ──────────────────────
describe('WorkflowStepsRenderer — Story 62.1 common parameters', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('AC1/AC2: does NOT show "Paramètres communs" when no shared parameter', () => {
    // Two steps, no shared params
    const actions: Record<number, CatalogActionDetail> = {
      1: { id: 1, name: 'Action A', parameters_schema: { properties: { param_a: {} } } } as unknown as CatalogActionDetail,
      2: { id: 2, name: 'Action B', parameters_schema: { properties: { param_b: {} } } } as unknown as CatalogActionDetail,
    };
    vi.mocked(extractParameterFields)
      .mockImplementationOnce(() => [{ name: 'param_a', label: 'Param A', type: 'string', required: false }] as ParameterField[])
      .mockImplementationOnce(() => [{ name: 'param_b', label: 'Param B', type: 'string', required: false }] as ParameterField[])
      // per-step rendering (no common names filtered)
      .mockImplementationOnce(() => [{ name: 'param_a', label: 'Param A', type: 'string', required: false }] as ParameterField[])
      .mockImplementationOnce(() => [{ name: 'param_b', label: 'Param B', type: 'string', required: false }] as ParameterField[]);

    renderComponent({
      workflowSteps: [
        { order: 1, name: 'Step 1', referenced_action_id: 1 },
        { order: 2, name: 'Step 2', referenced_action_id: 2 },
      ],
      workflowStepActions: actions,
    });

    expect(screen.queryByText('Paramètres communs')).not.toBeInTheDocument();
  });

  it('AC1: shows "Paramètres communs" section when two steps share a parameter', () => {
    const actions: Record<number, CatalogActionDetail> = {
      1: { id: 1, name: 'Action A', parameters_schema: {} } as unknown as CatalogActionDetail,
      2: { id: 2, name: 'Action B', parameters_schema: {} } as unknown as CatalogActionDetail,
    };
    const sharedField: ParameterField = { name: 'server_id', label: 'Server ID', type: 'string', required: false };

    vi.mocked(extractParameterFields)
      // extractCommonParameters calls (2 steps)
      .mockImplementationOnce(() => [sharedField, { name: 'specific_a', label: 'Specific A', type: 'string', required: false }] as ParameterField[])
      .mockImplementationOnce(() => [sharedField, { name: 'specific_b', label: 'Specific B', type: 'string', required: false }] as ParameterField[])
      // per-step rendering (2 steps)
      .mockImplementationOnce(() => [sharedField, { name: 'specific_a', label: 'Specific A', type: 'string', required: false }] as ParameterField[])
      .mockImplementationOnce(() => [sharedField, { name: 'specific_b', label: 'Specific B', type: 'string', required: false }] as ParameterField[]);

    renderComponent({
      workflowSteps: [
        { order: 1, name: 'Step 1', referenced_action_id: 1 },
        { order: 2, name: 'Step 2', referenced_action_id: 2 },
      ],
      workflowStepActions: actions,
    });

    expect(screen.getByText('Paramètres communs')).toBeInTheDocument();
    // The shared field label appears in the common section
    expect(screen.getByText('Server ID')).toBeInTheDocument();
  });

  it('AC4: shared parameter does NOT appear in per-step blocks', () => {
    const actions: Record<number, CatalogActionDetail> = {
      1: { id: 1, name: 'Action A', parameters_schema: {} } as unknown as CatalogActionDetail,
      2: { id: 2, name: 'Action B', parameters_schema: {} } as unknown as CatalogActionDetail,
    };
    const sharedField: ParameterField = { name: 'server_id', label: 'Server ID', type: 'string', required: false };
    const specificA: ParameterField = { name: 'specific_a', label: 'Specific A', type: 'string', required: false };
    const specificB: ParameterField = { name: 'specific_b', label: 'Specific B', type: 'string', required: false };

    vi.mocked(extractParameterFields)
      // extractCommonParameters
      .mockImplementationOnce(() => [sharedField, specificA])
      .mockImplementationOnce(() => [sharedField, specificB])
      // per-step rendering for step 1
      .mockImplementationOnce(() => [sharedField, specificA])
      // per-step rendering for step 2
      .mockImplementationOnce(() => [sharedField, specificB]);

    renderComponent({
      workflowSteps: [
        { order: 1, name: 'Step 1', referenced_action_id: 1 },
        { order: 2, name: 'Step 2', referenced_action_id: 2 },
      ],
      workflowStepActions: actions,
    });

    // 'Server ID' appears exactly once (in common section, not duplicated in steps)
    expect(screen.getAllByText('Server ID')).toHaveLength(1);
    // Step-specific params still appear
    expect(screen.getByText('Specific A')).toBeInTheDocument();
    expect(screen.getByText('Specific B')).toBeInTheDocument();
  });

  it('AC4: shows "all params are common" message when step has no remaining fields', () => {
    const actions: Record<number, CatalogActionDetail> = {
      1: { id: 1, name: 'Action A', parameters_schema: {} } as unknown as CatalogActionDetail,
      2: { id: 2, name: 'Action B', parameters_schema: {} } as unknown as CatalogActionDetail,
    };
    const sharedField: ParameterField = { name: 'server_id', label: 'Server ID', type: 'string', required: false };

    vi.mocked(extractParameterFields)
      // extractCommonParameters (both steps have only server_id)
      .mockImplementationOnce(() => [sharedField])
      .mockImplementationOnce(() => [sharedField])
      // per-step rendering (both steps return only server_id)
      .mockImplementationOnce(() => [sharedField])
      .mockImplementationOnce(() => [sharedField]);

    renderComponent({
      workflowSteps: [
        { order: 1, name: 'Step 1', referenced_action_id: 1 },
        { order: 2, name: 'Step 2', referenced_action_id: 2 },
      ],
      workflowStepActions: actions,
    });

    expect(screen.getAllByText('Tous les paramètres de cette étape sont définis dans la section Paramètres communs.')).toHaveLength(2);
  });

  it('AC2: does not show common section while loading actions', () => {
    renderComponent({
      loadingWorkflowStepActions: true,
    });

    expect(screen.queryByText('Paramètres communs')).not.toBeInTheDocument();
  });

  it('AC3: inventory field renders in common section (server selector)', () => {
    const actions: Record<number, CatalogActionDetail> = {
      1: { id: 1, name: 'Action A', parameters_schema: {} } as unknown as CatalogActionDetail,
      2: { id: 2, name: 'Action B', parameters_schema: {} } as unknown as CatalogActionDetail,
    };
    const inventoryField: ParameterField = {
      name: 'server_id',
      label: 'Serveur',
      type: 'string',
      required: false,
      inventorySource: 'servers',
    };

    vi.mocked(extractParameterFields)
      .mockImplementationOnce(() => [inventoryField])
      .mockImplementationOnce(() => [inventoryField])
      .mockImplementationOnce(() => [inventoryField])
      .mockImplementationOnce(() => [inventoryField]);

    const inventoryData = { servers: [{ id: '1', name: 'srv-01' } as never] };

    renderComponent({
      workflowSteps: [
        { order: 1, name: 'Step 1', referenced_action_id: 1 },
        { order: 2, name: 'Step 2', referenced_action_id: 2 },
      ],
      workflowStepActions: actions,
      inventoryData,
    });

    // Common section is visible
    expect(screen.getByText('Paramètres communs')).toBeInTheDocument();
    // Field label appears in common section
    expect(screen.getByText('Serveur')).toBeInTheDocument();
    // Verify renderFieldInput was called with the inventory field (AC3: same rendering as per-step)
    const calls = vi.mocked(renderFieldInput).mock.calls;
    const commonSectionCall = calls.find(([field]) => field.name === 'server_id' && field.inventorySource === 'servers');
    expect(commonSectionCall).toBeDefined();
    expect(commonSectionCall![0].inventorySource).toBe('servers');
    // inventoryData was forwarded to renderFieldInput
    expect(commonSectionCall![1]).toBe(inventoryData);
  });

  it('M2: same param name but different inventorySource → not common, both shown in per-step blocks', () => {
    // Step 1 has target|servers|, Step 2 has target||
    // These have different paramKeys → neither is common
    // Bug (pre-fix): with name-only filtering, the non-common target|| in step 2 would be hidden
    const actions: Record<number, CatalogActionDetail> = {
      1: { id: 1, name: 'Action A', parameters_schema: {} } as unknown as CatalogActionDetail,
      2: { id: 2, name: 'Action B', parameters_schema: {} } as unknown as CatalogActionDetail,
    };
    const targetWithInventory: ParameterField = { name: 'target', label: 'Target (server)', type: 'string', required: false, inventorySource: 'servers' };
    const targetWithout: ParameterField = { name: 'target', label: 'Target (plain)', type: 'string', required: false };

    vi.mocked(extractParameterFields)
      // extractCommonParameters: step 1 → target|servers|, step 2 → target||
      .mockImplementationOnce(() => [targetWithInventory])
      .mockImplementationOnce(() => [targetWithout])
      // per-step rendering: step 1, step 2
      .mockImplementationOnce(() => [targetWithInventory])
      .mockImplementationOnce(() => [targetWithout]);

    renderComponent({
      workflowSteps: [
        { order: 1, name: 'Step 1', referenced_action_id: 1 },
        { order: 2, name: 'Step 2', referenced_action_id: 2 },
      ],
      workflowStepActions: actions,
    });

    // No common section (different paramKeys)
    expect(screen.queryByText('Paramètres communs')).not.toBeInTheDocument();
    // Both per-step target fields are rendered (not incorrectly filtered out)
    expect(screen.getByText('Target (server)')).toBeInTheDocument();
    expect(screen.getByText('Target (plain)')).toBeInTheDocument();
  });
});

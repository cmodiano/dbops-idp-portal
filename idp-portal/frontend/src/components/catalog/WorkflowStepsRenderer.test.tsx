/**
 * Tests for WorkflowStepsRenderer component (Story 20.4, Task 2.3).
 *
 * Tests:
 * - Rendering workflow steps with action names
 * - Loading state display
 * - Error state display
 * - Validation error summary display
 * - Steps with no parameters show info alert
 */

import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { Form, App } from 'antd';
import { WorkflowStepsRenderer } from './WorkflowStepsRenderer';
import { extractParameterFields } from '../../hooks/useDynamicForm';
import type { ParameterField } from '../../hooks/useDynamicForm';
import type { CatalogActionDetail } from '../../services/catalog_service';

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
    vi.mocked(extractParameterFields).mockImplementationOnce(() => [
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
    ]);

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

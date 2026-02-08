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

// Wrapper providing Ant Design Form and App context
function Wrapper({ children }: { children: React.ReactNode }) {
  const [form] = Form.useForm();
  return (
    <App>
      <Form form={form}>{children}</Form>
    </App>
  );
}

const mockWorkflowSteps = [
  { order: 1, name: 'Stop DB', referenced_action_id: 101 },
  { order: 2, name: 'Patch', referenced_action_id: 102 },
];

const mockStepActions: Record<number, CatalogActionDetail> = {
  101: {
    id: 101,
    name: 'Stop Database',
    parameters_schema: { properties: { db_name: { title: 'Database Name', type: 'string' } } },
  } as CatalogActionDetail,
  102: {
    id: 102,
    name: 'Apply Patch',
    parameters_schema: null,
  } as CatalogActionDetail,
};

function renderComponent(overrides = {}) {
  const [form] = [null]; // Placeholder — form is provided by wrapper
  const defaultProps = {
    form: {} as ReturnType<typeof Form.useForm>[0],
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
function FormWrapper(props: Omit<Parameters<typeof WorkflowStepsRenderer>[0], 'form'> & { form?: unknown }) {
  const [form] = Form.useForm();
  return (
    <Form form={form}>
      <WorkflowStepsRenderer {...props} form={form} />
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

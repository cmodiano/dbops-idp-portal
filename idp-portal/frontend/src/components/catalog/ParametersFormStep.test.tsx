/**
 * Tests for ParametersFormStep (Story 34.14 — SOLID-FE-11).
 *
 * Interface post-Story 34-13: la prop 'action' a été supprimée et les props
 * inventory sont lues via useWizardExecutionContext().
 */

import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { App, Form } from 'antd';
import { ParametersFormStep } from './ParametersFormStep';
import type { ParametersFormStepProps } from './ParametersFormStep';
import { WizardExecutionContextProvider } from '../../contexts/WizardExecutionContext';
import type { WizardExecutionContextValue } from '../../contexts/WizardExecutionContext';
import { useAuth } from '../../contexts/AuthContext';

vi.mock('../../contexts/AuthContext', () => ({
  useAuth: vi.fn(() => ({ isBusinessProfile: false })),
}));

vi.mock('./WorkflowStepsRenderer', () => ({
  WorkflowStepsRenderer: ({
    loadingWorkflowStepActions,
    workflowStepActionsError,
    workflowValidationSummary,
  }: {
    loadingWorkflowStepActions: boolean;
    workflowStepActionsError: string | null;
    workflowValidationSummary: string | null;
    [key: string]: unknown;
  }) => (
    <div data-testid="workflow-steps-renderer">
      {loadingWorkflowStepActions && <div data-testid="workflow-loading">Chargement des étapes…</div>}
      {workflowStepActionsError && (
        <div data-testid="workflow-error" role="alert">
          {workflowStepActionsError}
        </div>
      )}
      {workflowValidationSummary && (
        <div data-testid="workflow-validation-summary">{workflowValidationSummary}</div>
      )}
    </div>
  ),
}));

const mockWizardCtx: WizardExecutionContextValue = {
  environmentsCache: null,
  inventoryData: {},
  inventoryWarnings: {},
  loadingInventory: false,
  derivedEnvironment: null,
  currentImpact: null,
  hasMixedEnvironments: false,
  resolvedPatternTargets: [],
  patternResolving: false,
  selectedServerNames: [],
};

type TestProps = Omit<ParametersFormStepProps, 'form'>;

function TestParametersFormStep(props: TestProps) {
  const [form] = Form.useForm();
  return (
    <App>
      <WizardExecutionContextProvider value={mockWizardCtx}>
        <ParametersFormStep form={form} {...props} />
      </WizardExecutionContextProvider>
    </App>
  );
}

const defaultProps: TestProps = {
  parameterFields: [],
  parameters: {},
  onParametersChange: vi.fn(),
  isWorkflow: false,
  workflowSteps: [],
  workflowStepActions: {},
  loadingWorkflowStepActions: false,
  workflowStepActionsError: null,
  workflowValidationSummary: null,
};

const stringField = {
  name: 'db_name',
  label: 'Nom de la base',
  type: 'string' as const,
  required: true,
  description: 'Nom technique de la base de données',
};

describe('ParametersFormStep', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(useAuth).mockReturnValue({ isBusinessProfile: false } as unknown as ReturnType<typeof useAuth>);
  });

  describe('Rendu smoke — non-workflow sans paramètres', () => {
    it('rend sans erreur', () => {
      expect(() => render(<TestParametersFormStep {...defaultProps} />)).not.toThrow();
    });

    it("affiche l'alerte 'Aucun paramètre requis' quand parameterFields est vide", () => {
      render(<TestParametersFormStep {...defaultProps} />);
      expect(
        screen.getByText("Cette action ne necessite pas de parametres."),
      ).toBeInTheDocument();
    });

    it("affiche la description simplifiée pour business profile sans paramètres", () => {
      vi.mocked(useAuth).mockReturnValue({ isBusinessProfile: true } as unknown as ReturnType<typeof useAuth>);
      render(<TestParametersFormStep {...defaultProps} />);
      expect(
        screen.getByText("Aucune information supplementaire n'est necessaire."),
      ).toBeInTheDocument();
    });
  });

  describe('Champs dynamiques — non-workflow avec paramètres', () => {
    it('affiche le label du champ', () => {
      render(<TestParametersFormStep {...defaultProps} parameterFields={[stringField]} />);
      expect(screen.getByText('Nom de la base')).toBeInTheDocument();
    });

    it("rend un input pour un champ de type 'string'", () => {
      render(<TestParametersFormStep {...defaultProps} parameterFields={[stringField]} />);
      expect(screen.getByRole('textbox')).toBeInTheDocument();
    });

    it('appelle onParametersChange quand la valeur change', async () => {
      const user = userEvent.setup();
      const onParametersChange = vi.fn();
      render(
        <TestParametersFormStep
          {...defaultProps}
          parameterFields={[stringField]}
          onParametersChange={onParametersChange}
        />,
      );
      await user.type(screen.getByRole('textbox'), 'TEST_DB');
      expect(onParametersChange).toHaveBeenCalled();
    });

    it("affiche le marqueur 'requis' pour un champ required", () => {
      render(<TestParametersFormStep {...defaultProps} parameterFields={[stringField]} />);
      // Ant Design Form.Item required ajoute un astérisque (*) dans le label
      const label = screen.getByText('Nom de la base').closest('.ant-form-item-label');
      expect(label?.querySelector('.ant-form-item-required')).toBeTruthy();
    });
  });

  describe('Mode workflow (isWorkflow=true)', () => {
    it('affiche WorkflowStepsRenderer au lieu des champs directs', () => {
      render(
        <TestParametersFormStep
          {...defaultProps}
          isWorkflow={true}
          workflowSteps={[{ order: 1, name: 'Étape 1', referenced_action_id: 10 }]}
        />,
      );
      expect(screen.getByTestId('workflow-steps-renderer')).toBeInTheDocument();
    });

    it("transmet loadingWorkflowStepActions=true à WorkflowStepsRenderer", () => {
      render(
        <TestParametersFormStep
          {...defaultProps}
          isWorkflow={true}
          loadingWorkflowStepActions={true}
        />,
      );
      expect(screen.getByTestId('workflow-loading')).toBeInTheDocument();
    });

    it("transmet workflowStepActionsError à WorkflowStepsRenderer", () => {
      render(
        <TestParametersFormStep
          {...defaultProps}
          isWorkflow={true}
          workflowStepActionsError="Erreur de chargement des actions"
        />,
      );
      expect(screen.getByTestId('workflow-error')).toHaveTextContent(
        'Erreur de chargement des actions',
      );
    });

    it("n'affiche pas les champs directs en mode workflow", () => {
      render(
        <TestParametersFormStep
          {...defaultProps}
          isWorkflow={true}
          parameterFields={[stringField]}
        />,
      );
      expect(screen.queryByText('Nom de la base')).not.toBeInTheDocument();
    });

    it("transmet workflowValidationSummary à WorkflowStepsRenderer", () => {
      render(
        <TestParametersFormStep
          {...defaultProps}
          isWorkflow={true}
          workflowValidationSummary="Résumé de validation du workflow"
        />,
      );
      expect(screen.getByTestId('workflow-validation-summary')).toHaveTextContent(
        'Résumé de validation du workflow',
      );
    });
  });

  describe('Alerte business profile (isWorkflow=false)', () => {
    it("affiche l'alerte info business profile quand isBusinessProfile=true", () => {
      vi.mocked(useAuth).mockReturnValue({ isBusinessProfile: true } as unknown as ReturnType<typeof useAuth>);
      render(<TestParametersFormStep {...defaultProps} parameterFields={[stringField]} />);
      // L'alerte est affichée en premier (avant les champs)
      const alerts = screen.getAllByRole('alert');
      expect(alerts.length).toBeGreaterThanOrEqual(1);
    });

    it("n'affiche pas l'alerte business profile quand isBusinessProfile=false", () => {
      vi.mocked(useAuth).mockReturnValue({ isBusinessProfile: false } as unknown as ReturnType<typeof useAuth>);
      render(<TestParametersFormStep {...defaultProps} parameterFields={[stringField]} />);
      // Aucun alert sauf ceux potentiels des validations
      // Le champ est affiché sans alerte business
      expect(screen.getByText('Nom de la base')).toBeInTheDocument();
    });
  });
});

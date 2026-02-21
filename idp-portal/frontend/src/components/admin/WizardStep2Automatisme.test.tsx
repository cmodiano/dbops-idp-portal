import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Form } from 'antd';
import { WizardStep2Automatisme } from './WizardStep2Automatisme';

vi.mock('../../hooks/useAAPTemplates', () => ({
  useAAPTemplates: vi.fn(() => ({
    templates: [],
    loading: false,
    fallback: false,
    error: null,
  })),
}));

vi.mock('../../contexts/ThemeContext', () => ({
  useTheme: () => ({ mode: 'light', effectiveMode: 'light', setMode: vi.fn(), toggleTheme: vi.fn() }),
}));

vi.mock('../../services/admin_service', () => ({
  getActions: vi.fn().mockResolvedValue([]),
  getWorkflowSteps: vi.fn().mockResolvedValue([]),
  getEligibleActionsForWorkflow: vi.fn().mockResolvedValue([]),
}));

const defaultProps = {
  isWorkflow: false,
  isReadOnly: false,
  isPlatformAAP: false,
  integrationId: undefined,
  aapResourceType: 'job_template' as const,
  setAapResourceType: vi.fn(),
  aapTemplateId: undefined,
  setAapTemplateId: vi.fn(),
  parameterList: [],
  setParameterList: vi.fn(),
  workflowSteps: [],
  setWorkflowSteps: vi.fn(),
  workflowViewMode: 'list' as const,
  setWorkflowViewMode: vi.fn(),
};

function renderWithForm(props = defaultProps) {
  return render(
    <Form>
      <WizardStep2Automatisme {...props} />
    </Form>
  );
}

describe('WizardStep2Automatisme', () => {
  it('affiche le label Paramètres pour une action non-AAP', () => {
    renderWithForm();
    expect(screen.getByText('Paramètres')).toBeInTheDocument();
  });

  it('affiche le sélecteur de type AAP quand isPlatformAAP=true', () => {
    renderWithForm({ ...defaultProps, isPlatformAAP: true, integrationId: 1 });
    expect(screen.getByText(/Quel automatisme appeler/i)).toBeInTheDocument();
    expect(screen.getByText(/Type de ressource/i)).toBeInTheDocument();
  });

  it('affiche le message info pour un workflow', () => {
    renderWithForm({ ...defaultProps, isWorkflow: true });
    expect(screen.getByText(/workflow enchaîne des actions existantes/i)).toBeInTheDocument();
  });

  it('affiche les boutons liste/visuel pour un workflow', () => {
    renderWithForm({ ...defaultProps, isWorkflow: true });
    expect(screen.getByRole('radio', { name: /Mode liste/i })).toBeInTheDocument();
    expect(screen.getByRole('radio', { name: /Mode visuel/i })).toBeInTheDocument();
  });

  it('appelle setWorkflowViewMode au clic sur Mode visuel', async () => {
    const setMode = vi.fn();
    const user = userEvent.setup({ pointerEventsCheck: 0 });
    renderWithForm({ ...defaultProps, isWorkflow: true, setWorkflowViewMode: setMode });
    await user.click(screen.getByRole('radio', { name: /Mode visuel/i }));
    expect(setMode).toHaveBeenCalledWith('visual');
  });
});

import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ActionFormCollapseSections, type ActionFormCollapseSectionsProps } from './ActionFormCollapseSections';
import { Form } from 'antd';

vi.mock('../../hooks/useEnvironments', () => ({
  useEnvironments: () => ({
    environments: ['DEV', 'STAGING', 'PROD'],
    loading: false,
    error: null,
    environmentOptions: [
      { value: 'DEV', label: 'DEV' },
      { value: 'STAGING', label: 'STAGING' },
      { value: 'PROD', label: 'PROD' },
    ],
  }),
  invalidateEnvironmentsCache: vi.fn(),
}));

vi.mock('../../contexts/ThemeContext', () => ({
  useTheme: () => ({ mode: 'light', effectiveMode: 'light', setMode: vi.fn(), toggleTheme: vi.fn() }),
}));

vi.mock('../common/SectionHelp', () => ({
  default: () => null,
}));

const defaultProps: ActionFormCollapseSectionsProps = {
  executionSteps: [],
  setExecutionSteps: vi.fn(),
  remediationRules: [],
  setRemediationRules: vi.fn(),
  editAction: null,
  watchedIntegrationId: undefined,
};

function renderWithForm(props: ActionFormCollapseSectionsProps = defaultProps) {
  return render(
    <Form>
      <ActionFormCollapseSections {...props} />
    </Form>
  );
}

describe('ActionFormCollapseSections', () => {
  it('affiche les 2 en-têtes de panneau (étapes, remédiation)', () => {
    renderWithForm();
    expect(screen.getByText(/Etapes d'execution et changement ServiceNow/i)).toBeInTheDocument();
    expect(screen.getByText(/Règles de remédiation automatique/i)).toBeInTheDocument();
  });

  it('affiche le compteur d\'étapes quand executionSteps non vide', () => {
    const props = {
      ...defaultProps,
      executionSteps: [
        { order: 1, name: 'Step 1', type: 'execution' as const, connector_type: 'none' as const, conditional_environments: null },
        { order: 2, name: 'Step 2', type: 'execution' as const, connector_type: 'none' as const, conditional_environments: null },
      ],
    };
    renderWithForm(props);
    expect(screen.getByText(/2 etapes/i)).toBeInTheDocument();
  });

  it('affiche le compteur de règles de remédiation', () => {
    const props = {
      ...defaultProps,
      remediationRules: [
        { id: '1', error_pattern: '.*', target_action_id: 1, environments: [], auto_trigger: false, risk_level: 'low' as const },
      ],
    };
    renderWithForm(props);
    expect(screen.getByText(/1 règle/i)).toBeInTheDocument();
  });

  it('ouvre le panneau étapes au clic', async () => {
    const user = userEvent.setup();
    renderWithForm();
    const stepHeader = screen.getByText(/Etapes d'execution et changement ServiceNow/i);
    await user.click(stepHeader);
    // Le contenu du panneau est rendu après clic : maintenant plusieurs éléments matchent
    expect(screen.getAllByText(/Etapes d'execution/i).length).toBeGreaterThan(1);
  });
});

import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { Form } from 'antd';
import { WizardStep3ImpactChangement, type WizardStep3ImpactChangementProps } from './WizardStep3ImpactChangement';

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

vi.mock('../../services/admin_service', () => ({
  getBusinessRulePolicies: vi.fn().mockResolvedValue([]),
}));

const defaultProps: WizardStep3ImpactChangementProps = {
  isWorkflow: false,
  isReadOnly: false,
  impactRulesList: [],
  setImpactRulesList: vi.fn(),
  defaultImpactLevel: null,
  setDefaultImpactLevel: vi.fn(),
  changeTypeConfig: {},
  setChangeTypeConfig: vi.fn(),
  gateConfig: null,
  setGateConfig: vi.fn(),
  businessRulePolicyId: null,
  setBusinessRulePolicyId: vi.fn(),
  notificationConfig: null,
  setNotificationConfig: vi.fn(),
  selectedIntegration: undefined,
  editAction: null,
  getIntegrationById: vi.fn(() => undefined),
};

function renderWithForm(props: WizardStep3ImpactChangementProps = defaultProps) {
  return render(
    <Form>
      <WizardStep3ImpactChangement {...props} />
    </Form>
  );
}

describe('WizardStep3ImpactChangement', () => {
  it('affiche la légende des niveaux d\'impact', () => {
    renderWithForm();
    expect(screen.getByText(/Signification des niveaux/i)).toBeInTheDocument();
    expect(screen.getByText(/Faible/i)).toBeInTheDocument();
  });

  it('affiche le sélecteur de niveau d\'impact par défaut', () => {
    renderWithForm();
    expect(screen.getByText(/Niveau d'impact par défaut/i)).toBeInTheDocument();
  });

  it('affiche la section Gates et ServiceNow pour une action', () => {
    renderWithForm();
    expect(screen.getByText(/Gates et Changement ServiceNow/i)).toBeInTheDocument();
  });

  it('masque la section ServiceNow pour un workflow', () => {
    renderWithForm({ ...defaultProps, isWorkflow: true });
    expect(screen.queryByText(/Gates et Changement ServiceNow/i)).not.toBeInTheDocument();
  });

  it('affiche les sections Règles métier et Notifications', () => {
    renderWithForm();
    expect(screen.getByText('Règles métier')).toBeInTheDocument();
    expect(screen.getByText('Notifications')).toBeInTheDocument();
  });

  it('affiche les règles d\'impact existantes', () => {
    const props = {
      ...defaultProps,
      impactRulesList: [{ environment: 'PROD', level: 'high' as const, criteria: null }],
    };
    renderWithForm(props);
    expect(screen.getByText('Regle 1')).toBeInTheDocument();
  });
});

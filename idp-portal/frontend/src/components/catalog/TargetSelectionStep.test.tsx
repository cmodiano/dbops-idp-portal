/**
 * Tests for TargetSelectionStep component (Story 21.5).
 * Tests dynamic environment labels, no hardcoded fallback, and case-insensitive production detection.
 */

import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { App } from 'antd';
import { TargetSelectionStep, type TargetSelectionStepProps } from './TargetSelectionStep';
import type { InventoryItem, ImpactLevel } from '../../types/api';
import { WizardExecutionContextProvider, type WizardExecutionContextValue } from '../../contexts/WizardExecutionContext';

// Mock TargetSelector to avoid API calls
vi.mock('./TargetSelector', () => ({
  TargetSelector: ({ placeholder }: { placeholder?: string }) => (
    <div data-testid="target-selector">{placeholder}</div>
  ),
}));

const defaultWizardContext: WizardExecutionContextValue = {
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

function TestWrapper({ children, contextValue = defaultWizardContext }: { children: React.ReactNode; contextValue?: WizardExecutionContextValue }) {
  return (
    <App>
      <WizardExecutionContextProvider value={contextValue}>
        {children}
      </WizardExecutionContextProvider>
    </App>
  );
}

const mockAction = {
  id: 1,
  name: 'Test Action',
  description: 'Test',
  engine: 'Oracle',
  platform: 'AAP',
  parameters_schema: {},
  impact_rules: {},
  default_impact_level: 'low' as ImpactLevel,
  status: 'published' as const,
  requires_target: false,
  change_type_config: {},
  execution_count: 0,
  tags: [],
  is_favorite: false,
  icon_url: null,
  owner: 'admin',
  created_at: '',
  updated_at: '',
  resource_type: 'job_template' as const,
  category_id: null,
  category_name: null,
  allowed_environments: [],
  integration_id: null,
  requires_approval: false,
  approval_groups: [],
} as unknown as TargetSelectionStepProps['action'];

const defaultProps: TargetSelectionStepProps = {
  action: mockAction,
  allowedEnvironments: ['developpement', 'certification', 'production', 'lab', 'qa'],
  selectedTargets: [],
  onTargetsChange: vi.fn(),
  targetInputMode: 'list',
  onTargetInputModeChange: vi.fn(),
  targetPattern: '',
  onTargetPatternChange: vi.fn(),
  manualTargetInput: '',
  onManualTargetInputChange: vi.fn(),
  selectedEnvironment: null,
  onEnvironmentChange: vi.fn(),
};

describe('TargetSelectionStep - Story 21.5', () => {
  describe('Environment cache display (AC #1)', () => {
    it('displays environment options from cache', () => {
      const cache: InventoryItem[] = [
        { id: 'developpement', name: 'Développement', environment: null },
        { id: 'lab', name: 'Lab', environment: null },
        { id: 'qa', name: 'QA', environment: null },
      ];

      render(
        <TestWrapper contextValue={{ ...defaultWizardContext, environmentsCache: cache }}>
          <TargetSelectionStep {...defaultProps} />
        </TestWrapper>
      );

      // Select should show the options (env names from cache)
      expect(screen.getByRole('combobox')).toBeInTheDocument();
    });

    it('shows loading placeholder when cache is null', () => {
      render(
        <TestWrapper contextValue={{ ...defaultWizardContext, environmentsCache: null }}>
          <TargetSelectionStep {...defaultProps} />
        </TestWrapper>
      );

      expect(screen.getByText('Chargement...')).toBeInTheDocument();
    });

    it('shows "Aucun environnement disponible" when cache is empty', () => {
      render(
        <TestWrapper contextValue={{ ...defaultWizardContext, environmentsCache: [] }}>
          <TargetSelectionStep {...defaultProps} />
        </TestWrapper>
      );

      expect(screen.getByText('Aucun environnement disponible')).toBeInTheDocument();
    });

    it('disables select when no allowed environments match cache', () => {
      const cache: InventoryItem[] = [
        { id: 'certif', name: 'Certif', environment: null },
      ];

      render(
        <TestWrapper contextValue={{ ...defaultWizardContext, environmentsCache: cache }}>
          <TargetSelectionStep
            {...defaultProps}
            allowedEnvironments={['developpement', 'certification']}
          />
        </TestWrapper>
      );

      const selectWrapper = screen.getByRole('combobox').closest('.ant-select');
      expect(selectWrapper).toHaveClass('ant-select-disabled');
    });
  });

  describe('Production warning (AC #5)', () => {
    it('shows production warning for prod environment', () => {
      render(
        <TestWrapper contextValue={{ ...defaultWizardContext, derivedEnvironment: 'production', environmentsCache: [] }}>
          <TargetSelectionStep {...defaultProps} />
        </TestWrapper>
      );

      expect(screen.getByText('Avertissement - Environnement Production')).toBeInTheDocument();
    });

    it('shows production warning for PROD (case-insensitive)', () => {
      render(
        <TestWrapper contextValue={{ ...defaultWizardContext, derivedEnvironment: 'PROD', environmentsCache: [] }}>
          <TargetSelectionStep {...defaultProps} />
        </TestWrapper>
      );

      expect(screen.getByText('Avertissement - Environnement Production')).toBeInTheDocument();
    });

    it('shows production warning for prod alias', () => {
      render(
        <TestWrapper contextValue={{ ...defaultWizardContext, derivedEnvironment: 'prod', environmentsCache: [] }}>
          <TargetSelectionStep {...defaultProps} />
        </TestWrapper>
      );

      expect(screen.getByText('Avertissement - Environnement Production')).toBeInTheDocument();
    });

    it('does not show production warning for non-prod environments', () => {
      render(
        <TestWrapper contextValue={{ ...defaultWizardContext, derivedEnvironment: 'lab', environmentsCache: [] }}>
          <TargetSelectionStep {...defaultProps} />
        </TestWrapper>
      );

      expect(screen.queryByText('Avertissement - Environnement Production')).not.toBeInTheDocument();
    });
  });

  describe('Derived environment label (AC #2)', () => {
    it('displays derived environment with correct label for standard env', () => {
      render(
        <TestWrapper contextValue={{ ...defaultWizardContext, derivedEnvironment: 'developpement', environmentsCache: [] }}>
          <TargetSelectionStep
            {...defaultProps}
            action={{ ...mockAction, requires_target: true }}
          />
        </TestWrapper>
      );

      expect(screen.getByText(/Environnement derive : Développement/)).toBeInTheDocument();
    });

    it('displays derived environment with capitalized label for non-standard env', () => {
      render(
        <TestWrapper contextValue={{ ...defaultWizardContext, derivedEnvironment: 'lab', environmentsCache: [] }}>
          <TargetSelectionStep
            {...defaultProps}
            action={{ ...mockAction, requires_target: true }}
          />
        </TestWrapper>
      );

      expect(screen.getByText(/Environnement derive : Lab/)).toBeInTheDocument();
    });

    it('displays derived environment with capitalized label for qa', () => {
      render(
        <TestWrapper contextValue={{ ...defaultWizardContext, derivedEnvironment: 'qa', environmentsCache: [] }}>
          <TargetSelectionStep
            {...defaultProps}
            action={{ ...mockAction, requires_target: true }}
          />
        </TestWrapper>
      );

      expect(screen.getByText(/Environnement derive : Qa/)).toBeInTheDocument();
    });
  });

  describe('No hardcoded fallback (AC #1)', () => {
    it('does not render dev/staging/prod options when cache is empty', () => {
      render(
        <TestWrapper contextValue={{ ...defaultWizardContext, environmentsCache: [] }}>
          <TargetSelectionStep {...defaultProps} />
        </TestWrapper>
      );

      // With empty cache, no options should be in the dropdown
      expect(screen.queryByText('Développement')).not.toBeInTheDocument();
      expect(screen.queryByText('Staging')).not.toBeInTheDocument();
      expect(screen.queryByText('Production')).not.toBeInTheDocument();
    });
  });

  describe('Non-standard environments (AC #5)', () => {
    it('renders without errors with non-standard environment cache', () => {
      const cache: InventoryItem[] = [
        { id: 'uat', name: 'UAT', environment: null },
        { id: 'certif', name: 'Certif', environment: null },
      ];

      expect(() => {
        render(
          <TestWrapper contextValue={{ ...defaultWizardContext, environmentsCache: cache }}>
            <TargetSelectionStep
              {...defaultProps}
              allowedEnvironments={['uat', 'certif']}
            />
          </TestWrapper>
        );
      }).not.toThrow();
    });
  });
});

describe('TargetSelectionStep — coverage extension', () => {
  it('shows target selector when requires_target=true and mode=list', () => {
    render(
      <TestWrapper>
        <TargetSelectionStep
          {...defaultProps}
          action={{ ...mockAction, requires_target: true }}
          targetInputMode="list"
        />
      </TestWrapper>
    );
    expect(screen.getByTestId('target-selector')).toBeInTheDocument();
  });

  it('shows pattern input when requires_target=true and mode=pattern', () => {
    render(
      <TestWrapper>
        <TargetSelectionStep
          {...defaultProps}
          action={{ ...mockAction, requires_target: true }}
          targetInputMode="pattern"
        />
      </TestWrapper>
    );
    expect(screen.getByLabelText('Pattern de cibles')).toBeInTheDocument();
  });

  it('shows manual textarea when requires_target=true and mode=manual', () => {
    render(
      <TestWrapper>
        <TargetSelectionStep
          {...defaultProps}
          action={{ ...mockAction, requires_target: true }}
          targetInputMode="manual"
        />
      </TestWrapper>
    );
    expect(screen.getByLabelText('Liste des cibles')).toBeInTheDocument();
  });

  it('shows manual target count when manualTargetInput has content', () => {
    render(
      <TestWrapper>
        <TargetSelectionStep
          {...defaultProps}
          action={{ ...mockAction, requires_target: true }}
          targetInputMode="manual"
          manualTargetInput="srv-01, srv-02, srv-03"
        />
      </TestWrapper>
    );
    expect(screen.getByText(/3 cible\(s\) detectee\(s\)/)).toBeInTheDocument();
  });

  it('shows hasMixedEnvironments warning when true', () => {
    render(
      <TestWrapper contextValue={{ ...defaultWizardContext, hasMixedEnvironments: true }}>
        <TargetSelectionStep
          {...defaultProps}
          action={{ ...mockAction, requires_target: true }}
        />
      </TestWrapper>
    );
    expect(screen.getByText('Attention')).toBeInTheDocument();
    expect(screen.getByText(/environnements differents/i)).toBeInTheDocument();
  });

  it('shows resolved pattern count when pattern matches targets', () => {
    const resolvedTargets = [
      { id: 'srv-01', name: 'srv-01', environment: 'dev' },
      { id: 'srv-02', name: 'srv-02', environment: 'dev' },
    ];

    render(
      <TestWrapper contextValue={{ ...defaultWizardContext, resolvedPatternTargets: resolvedTargets, patternResolving: false }}>
        <TargetSelectionStep
          {...defaultProps}
          action={{ ...mockAction, requires_target: true }}
          targetInputMode="pattern"
          targetPattern="srv-*"
        />
      </TestWrapper>
    );
    expect(screen.getByText(/2 cible\(s\) correspondante\(s\)/)).toBeInTheDocument();
  });

  it('shows LoadingOutlined spinner when patternResolving=true', () => {
    render(
      <TestWrapper contextValue={{ ...defaultWizardContext, patternResolving: true }}>
        <TargetSelectionStep
          {...defaultProps}
          action={{ ...mockAction, requires_target: true }}
          targetInputMode="pattern"
          targetPattern="srv-*"
        />
      </TestWrapper>
    );
    // LoadingOutlined renders as anticon-loading
    expect(document.querySelector('.anticon-loading')).toBeInTheDocument();
  });

  it('shows inventory warning badge when inventoryWarnings.environments is true', () => {
    render(
      <TestWrapper contextValue={{ ...defaultWizardContext, inventoryWarnings: { environments: true }, environmentsCache: [] }}>
        <TargetSelectionStep {...defaultProps} />
      </TestWrapper>
    );
    expect(screen.getByText(/Données inventaire temporairement indisponibles/)).toBeInTheDocument();
  });

  it('shows auto-selection success alert when single allowed env and env selected', () => {
    const cache: InventoryItem[] = [{ id: 'dev', name: 'Développement', environment: null }];
    render(
      <TestWrapper contextValue={{ ...defaultWizardContext, environmentsCache: cache }}>
        <TargetSelectionStep
          {...defaultProps}
          allowedEnvironments={['dev']}
          selectedEnvironment={'dev' as unknown as TargetSelectionStepProps['selectedEnvironment']}
        />
      </TestWrapper>
    );
    expect(screen.getByText(/Environnement selectionne automatiquement/)).toBeInTheDocument();
  });

  it('shows impact level when currentImpact is not null', () => {
    render(
      <TestWrapper contextValue={{ ...defaultWizardContext, currentImpact: 'high' }}>
        <TargetSelectionStep {...defaultProps} />
      </TestWrapper>
    );
    expect(screen.getByText("Niveau d'impact:")).toBeInTheDocument();
  });

  it('renders target mode radio group when requires_target=true', () => {
    render(
      <TestWrapper>
        <TargetSelectionStep
          {...defaultProps}
          action={{ ...mockAction, requires_target: true }}
        />
      </TestWrapper>
    );
    // Radio.Group with mode options renders
    expect(screen.getByRole('radio', { name: 'Liste' })).toBeInTheDocument();
    expect(screen.getByRole('radio', { name: 'Pattern' })).toBeInTheDocument();
    expect(screen.getByRole('radio', { name: 'Saisie manuelle' })).toBeInTheDocument();
  });

  it('appelle onTargetInputModeChange quand un radio est cliqué (line 115)', () => {
    const onTargetInputModeChange = vi.fn();
    render(
      <TestWrapper>
        <TargetSelectionStep
          {...defaultProps}
          action={{ ...mockAction, requires_target: true }}
          onTargetInputModeChange={onTargetInputModeChange}
          targetInputMode="list"
        />
      </TestWrapper>
    );
    // Click the "Pattern" radio button to trigger Radio.Group onChange
    const patternRadio = screen.getByRole('radio', { name: 'Pattern' });
    fireEvent.click(patternRadio);
    expect(onTargetInputModeChange).toHaveBeenCalledWith('pattern');
  });

  it('appelle onTargetPatternChange quand le pattern input change (line 151)', () => {
    const onTargetPatternChange = vi.fn();
    render(
      <TestWrapper>
        <TargetSelectionStep
          {...defaultProps}
          action={{ ...mockAction, requires_target: true }}
          targetInputMode="pattern"
          onTargetPatternChange={onTargetPatternChange}
        />
      </TestWrapper>
    );
    const patternInput = screen.getByLabelText('Pattern de cibles');
    fireEvent.change(patternInput, { target: { value: 'srv-*' } });
    expect(onTargetPatternChange).toHaveBeenCalledWith('srv-*');
  });

  it('appelle onManualTargetInputChange quand le textarea change (line 174)', () => {
    const onManualTargetInputChange = vi.fn();
    render(
      <TestWrapper>
        <TargetSelectionStep
          {...defaultProps}
          action={{ ...mockAction, requires_target: true }}
          targetInputMode="manual"
          onManualTargetInputChange={onManualTargetInputChange}
        />
      </TestWrapper>
    );
    const textarea = screen.getByLabelText('Liste des cibles');
    fireEvent.change(textarea, { target: { value: 'srv-01, srv-02' } });
    expect(onManualTargetInputChange).toHaveBeenCalledWith('srv-01, srv-02');
  });

  it('affiche résultats pattern avec >5 cibles (truncated with "...") (line 159)', () => {
    const resolvedTargets = [
      { id: 'srv-01', name: 'srv-01', environment: 'dev' },
      { id: 'srv-02', name: 'srv-02', environment: 'dev' },
      { id: 'srv-03', name: 'srv-03', environment: 'dev' },
      { id: 'srv-04', name: 'srv-04', environment: 'dev' },
      { id: 'srv-05', name: 'srv-05', environment: 'dev' },
      { id: 'srv-06', name: 'srv-06', environment: 'dev' },
    ];

    render(
      <TestWrapper contextValue={{ ...defaultWizardContext, resolvedPatternTargets: resolvedTargets, patternResolving: false }}>
        <TargetSelectionStep
          {...defaultProps}
          action={{ ...mockAction, requires_target: true }}
          targetInputMode="pattern"
          targetPattern="srv-*"
        />
      </TestWrapper>
    );
    // More than 5 targets — should show "..."
    expect(screen.getByText(/6 cible\(s\) correspondante\(s\)/)).toBeInTheDocument();
    expect(screen.getByText(/\.\.\./)).toBeInTheDocument();
  });
});

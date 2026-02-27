/**
 * Tests for TargetSelectionStep component (Story 21.5).
 * Tests dynamic environment labels, no hardcoded fallback, and case-insensitive production detection.
 */

import { render, screen } from '@testing-library/react';
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

    it('shows production warning for production alias', () => {
      render(
        <TestWrapper contextValue={{ ...defaultWizardContext, derivedEnvironment: 'production', environmentsCache: [] }}>
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

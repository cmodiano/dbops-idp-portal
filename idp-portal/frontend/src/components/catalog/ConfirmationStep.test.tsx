/**
 * Tests for ConfirmationStep component (Story 21.5).
 * Tests dynamic environment labels, badge colors, and case-insensitive production detection.
 */

import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { App } from 'antd';
import { ConfirmationStep, type ConfirmationStepProps } from './ConfirmationStep';
import type { InventoryItem, ImpactLevel } from '../../types/api';
import { WizardExecutionContextProvider, type WizardExecutionContextValue } from '../../contexts/WizardExecutionContext';

// Mock SchedulingPanel to avoid complex dependency chain
vi.mock('./SchedulingPanel', () => ({
  SchedulingPanel: () => <div data-testid="scheduling-panel" />,
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
} as unknown as ConfirmationStepProps['action'];

const defaultProps: ConfirmationStepProps = {
  action: mockAction,
  selectedTargets: [],
  parameters: {},
  submitError: null,
  isScheduling: false,
  scheduling: { mode: 'immediate' } as unknown as ConfirmationStepProps['scheduling'],
  onSchedulingChange: vi.fn(),
  schedulingError: null,
  submitting: false,
  schedulingValidation: { isValid: true, errors: [] } as unknown as ConfirmationStepProps['schedulingValidation'],
  pageMeEnabled: false,
  onPageMeChange: vi.fn(),
};

describe('ConfirmationStep - Story 21.5', () => {
  describe('Environment label display (AC #2)', () => {
    it('displays environment name from cache when available', () => {
      const cache: InventoryItem[] = [
        { id: 'dev', name: 'Développement', environment: null },
      ];

      render(
        <TestWrapper contextValue={{ ...defaultWizardContext, derivedEnvironment: 'dev', environmentsCache: cache }}>
          <ConfirmationStep {...defaultProps} />
        </TestWrapper>
      );

      expect(screen.getByText('Développement')).toBeInTheDocument();
    });

    it('falls back to getEnvironmentLabel when env not in cache', () => {
      render(
        <TestWrapper contextValue={{ ...defaultWizardContext, derivedEnvironment: 'dev', environmentsCache: [] }}>
          <ConfirmationStep {...defaultProps} />
        </TestWrapper>
      );

      expect(screen.getByText('Développement')).toBeInTheDocument();
    });

    it('displays capitalized label for non-standard environment', () => {
      render(
        <TestWrapper contextValue={{ ...defaultWizardContext, derivedEnvironment: 'lab', environmentsCache: [] }}>
          <ConfirmationStep {...defaultProps} />
        </TestWrapper>
      );

      expect(screen.getByText('Lab')).toBeInTheDocument();
    });

    it('displays cache name for non-standard environment when in cache', () => {
      const cache: InventoryItem[] = [
        { id: 'lab', name: 'Laboratoire', environment: null },
      ];

      render(
        <TestWrapper contextValue={{ ...defaultWizardContext, derivedEnvironment: 'lab', environmentsCache: cache }}>
          <ConfirmationStep {...defaultProps} />
        </TestWrapper>
      );

      expect(screen.getByText('Laboratoire')).toBeInTheDocument();
    });
  });

  describe('Badge status (AC #4, #5)', () => {
    it('shows warning badge for production environment', () => {
      render(
        <TestWrapper contextValue={{ ...defaultWizardContext, derivedEnvironment: 'prod', environmentsCache: [] }}>
          <ConfirmationStep {...defaultProps} />
        </TestWrapper>
      );

      const badge = screen.getByText('Production').closest('.ant-badge');
      expect(badge).toBeTruthy();
      const dot = badge?.querySelector('.ant-badge-status-dot');
      expect(dot).toHaveClass('ant-badge-status-warning');
    });

    it('shows warning badge for PROD (case-insensitive)', () => {
      render(
        <TestWrapper contextValue={{ ...defaultWizardContext, derivedEnvironment: 'PROD', environmentsCache: [] }}>
          <ConfirmationStep {...defaultProps} />
        </TestWrapper>
      );

      const badge = screen.getByText('Production').closest('.ant-badge');
      expect(badge).toBeTruthy();
      const dot = badge?.querySelector('.ant-badge-status-dot');
      expect(dot).toHaveClass('ant-badge-status-warning');
    });

    it('shows processing badge for non-production environment', () => {
      render(
        <TestWrapper contextValue={{ ...defaultWizardContext, derivedEnvironment: 'dev', environmentsCache: [] }}>
          <ConfirmationStep {...defaultProps} />
        </TestWrapper>
      );

      const badge = screen.getByText('Développement').closest('.ant-badge');
      expect(badge).toBeTruthy();
      const dot = badge?.querySelector('.ant-badge-status-dot');
      expect(dot).toHaveClass('ant-badge-status-processing');
    });

    it('shows processing badge for lab environment', () => {
      render(
        <TestWrapper contextValue={{ ...defaultWizardContext, derivedEnvironment: 'lab', environmentsCache: [] }}>
          <ConfirmationStep {...defaultProps} />
        </TestWrapper>
      );

      const badge = screen.getByText('Lab').closest('.ant-badge');
      expect(badge).toBeTruthy();
      const dot = badge?.querySelector('.ant-badge-status-dot');
      expect(dot).toHaveClass('ant-badge-status-processing');
    });
  });

  describe('Non-standard environments in recap (AC #5)', () => {
    it('renders non-standard environments without errors', () => {
      expect(() => {
        render(
          <TestWrapper contextValue={{ ...defaultWizardContext, derivedEnvironment: 'uat', environmentsCache: [] }}>
            <ConfirmationStep {...defaultProps} />
          </TestWrapper>
        );
      }).not.toThrow();

      expect(screen.getByText('Uat')).toBeInTheDocument();
    });

    it('displays qa environment correctly', () => {
      render(
        <TestWrapper contextValue={{ ...defaultWizardContext, derivedEnvironment: 'qa', environmentsCache: [] }}>
          <ConfirmationStep {...defaultProps} />
        </TestWrapper>
      );

      expect(screen.getByText('Qa')).toBeInTheDocument();
    });
  });
});

describe('ConfirmationStep - Story 31.8 page_me', () => {
  const actionWithPageMe = {
    ...mockAction,
    notification_config: {
      channels: [],
      page_individual_enabled: true,
    },
  } as unknown as ConfirmationStepProps['action'];

  it('does not show page_me checkbox when notification_config is null', () => {
    render(
      <TestWrapper>
        <ConfirmationStep {...defaultProps} />
      </TestWrapper>,
    );
    expect(screen.queryByRole('checkbox')).not.toBeInTheDocument();
  });

  it('does not show page_me checkbox when page_individual_enabled is false', () => {
    const action = {
      ...mockAction,
      notification_config: {
        channels: [],
        page_individual_enabled: false,
      },
    } as unknown as ConfirmationStepProps['action'];
    render(
      <TestWrapper>
        <ConfirmationStep {...defaultProps} action={action} />
      </TestWrapper>,
    );
    expect(screen.queryByRole('checkbox')).not.toBeInTheDocument();
  });

  it('shows page_me checkbox when page_individual_enabled is true', () => {
    render(
      <TestWrapper>
        <ConfirmationStep {...defaultProps} action={actionWithPageMe} />
      </TestWrapper>,
    );
    expect(screen.getByRole('checkbox')).toBeInTheDocument();
    expect(screen.getByText(/pagé en cas d'échec/i)).toBeInTheDocument();
  });

  it('checkbox is unchecked when pageMeEnabled is false', () => {
    render(
      <TestWrapper>
        <ConfirmationStep {...defaultProps} action={actionWithPageMe} pageMeEnabled={false} />
      </TestWrapper>,
    );
    expect(screen.getByRole('checkbox')).not.toBeChecked();
  });

  it('checkbox is checked when pageMeEnabled is true', () => {
    render(
      <TestWrapper>
        <ConfirmationStep {...defaultProps} action={actionWithPageMe} pageMeEnabled={true} />
      </TestWrapper>,
    );
    expect(screen.getByRole('checkbox')).toBeChecked();
  });

  it('calls onPageMeChange when checkbox is clicked', () => {
    const onPageMeChange = vi.fn();
    render(
      <TestWrapper>
        <ConfirmationStep
          {...defaultProps}
          action={actionWithPageMe}
          onPageMeChange={onPageMeChange}
        />
      </TestWrapper>,
    );
    fireEvent.click(screen.getByRole('checkbox'));
    expect(onPageMeChange).toHaveBeenCalledWith(true);
  });
});

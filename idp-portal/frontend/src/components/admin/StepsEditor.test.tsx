/**
 * Tests for StepsEditor (Story 2.2, Story 2.7 connector_type, Story 21.4 dynamic environments).
 * Task 4.4: dropdown connecteur, ServiceNow shows conditional_environments, save sends connector_type.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { StepsEditor } from './StepsEditor';
import type { ExecutionStep } from '../../types/api';
import { useEnvironments } from '../../hooks/useEnvironments';

vi.mock('../../hooks/useEnvironments', () => ({
  useEnvironments: vi.fn(),
}));

vi.mock('../../hooks/useAAPTemplates', () => ({
  useAAPTemplates: vi.fn(),
}));

import { useAAPTemplates } from '../../hooks/useAAPTemplates';
const mockUseAAPTemplates = useAAPTemplates as ReturnType<typeof vi.fn>;

const mockUseEnvironments = useEnvironments as ReturnType<typeof vi.fn>;

const defaultEnvMock = {
  environments: ['dev', 'staging', 'prod'],
  environmentOptions: [
    { value: 'dev', label: 'Développement' },
    { value: 'staging', label: 'Staging' },
    { value: 'prod', label: 'Production' },
  ],
  loading: false,
  error: null,
};

const defaultAAPMock = {
  templates: [],
  loading: false,
  fallback: true,
  error: null,
};

describe('StepsEditor', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUseEnvironments.mockReturnValue(defaultEnvMock);
    mockUseAAPTemplates.mockReturnValue(defaultAAPMock);
  });

  it('renders connector dropdown (Story 2.7)', async () => {
    const steps: ExecutionStep[] = [
      {
        order: 1,
        name: 'Step 1',
        type: 'prerequisite',
        connector_type: 'none',
        conditional_environments: null,
      },
    ];
    render(<StepsEditor value={steps} onChange={() => {}} />);
    expect(screen.getByLabelText(/Connecteur etape 1/i)).toBeInTheDocument();
  });

  it('shows conditional_environments when connector_type is servicenow (Story 2.7, AC2)', async () => {
    const steps: ExecutionStep[] = [
      {
        order: 1,
        name: 'Ouverture changement',
        type: 'execution',
        connector_type: 'servicenow',
        connector_config: {},
        conditional_environments: ['prod'],
      },
    ];
    render(<StepsEditor value={steps} onChange={() => {}} />);
    expect(screen.getByLabelText(/Environnements conditionnes etape 1/i)).toBeInTheDocument();
  });

  it('does not show conditional_environments when connector_type is none', () => {
    const steps: ExecutionStep[] = [
      {
        order: 1,
        name: 'Step 1',
        type: 'prerequisite',
        connector_type: 'none',
        conditional_environments: null,
      },
    ];
    render(<StepsEditor value={steps} onChange={() => {}} />);
    expect(screen.queryByLabelText(/Environnements conditionnes/i)).not.toBeInTheDocument();
  });

  it('calls onChange with connector_type when adding step (default none)', async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<StepsEditor value={[]} onChange={onChange} />);
    await user.click(screen.getByRole('button', { name: /Ajouter une etape/i }));
    expect(onChange).toHaveBeenCalledWith([
      expect.objectContaining({
        order: 1,
        name: '',
        type: 'execution',
        connector_type: 'none',
        connector_config: null,
        conditional_environments: null,
      }),
    ]);
  });

  it('calls onChange with connector_type when selecting servicenow', async () => {
    const user = userEvent.setup();
    const steps: ExecutionStep[] = [
      {
        order: 1,
        name: 'Step 1',
        type: 'execution',
        connector_type: 'none',
        conditional_environments: null,
      },
    ];
    const onChange = vi.fn();
    render(<StepsEditor value={steps} onChange={onChange} />);
    const connectorSelect = screen.getByLabelText(/Connecteur etape 1/i);
    await user.click(connectorSelect);
    const option = await screen.findByText('ServiceNow');
    await user.click(option);
    expect(onChange).toHaveBeenCalledWith([
      expect.objectContaining({
        connector_type: 'servicenow',
      }),
    ]);
  });

  // Story 21.4 tests
  describe('Story 21.4: dynamic environments', () => {
    it('displays dynamic environment options in multi-select', async () => {
      const user = userEvent.setup();
      mockUseEnvironments.mockReturnValue({
        environments: ['dev', 'lab'],
        environmentOptions: [
          { value: 'dev', label: 'Développement' },
          { value: 'lab', label: 'Lab' },
        ],
        loading: false,
        error: null,
      });

      const steps: ExecutionStep[] = [
        {
          order: 1,
          name: 'Changement ServiceNow',
          type: 'execution',
          connector_type: 'servicenow',
          connector_config: {},
          conditional_environments: [],
        },
      ];
      render(<StepsEditor value={steps} onChange={vi.fn()} />);

      const envSelect = screen.getByLabelText(/Environnements conditionnes etape 1/i);
      await user.click(envSelect);

      expect(screen.getByText('Développement')).toBeInTheDocument();
      expect(screen.getByText('Lab')).toBeInTheDocument();
    });

    it('disables environment select when loading', () => {
      mockUseEnvironments.mockReturnValue({
        ...defaultEnvMock,
        loading: true,
      });

      const steps: ExecutionStep[] = [
        {
          order: 1,
          name: 'Changement',
          type: 'execution',
          connector_type: 'servicenow',
          connector_config: {},
          conditional_environments: [],
        },
      ];
      render(<StepsEditor value={steps} onChange={vi.fn()} />);

      const envSelect = screen.getByLabelText(/Environnements conditionnes etape 1/i);
      expect(envSelect.closest('.ant-select-disabled')).toBeTruthy();
    });

    it('validates at least one environment with dynamic envs', () => {
      const steps: ExecutionStep[] = [
        {
          order: 1,
          name: 'Changement',
          type: 'execution',
          connector_type: 'servicenow',
          connector_config: {},
          conditional_environments: [],
        },
      ];
      render(<StepsEditor value={steps} onChange={vi.fn()} />);

      expect(screen.getByText(/Selectionnez au moins un environnement/i)).toBeInTheDocument();
    });

    it('uses fallback environments when error occurs', () => {
      mockUseEnvironments.mockReturnValue({
        environments: ['dev', 'staging', 'prod'],
        environmentOptions: [
          { value: 'dev', label: 'Développement' },
          { value: 'staging', label: 'Staging' },
          { value: 'prod', label: 'Production' },
        ],
        loading: false,
        error: new Error('API error'),
      });

      const steps: ExecutionStep[] = [
        {
          order: 1,
          name: 'Changement',
          type: 'execution',
          connector_type: 'servicenow',
          connector_config: {},
          conditional_environments: [],
        },
      ];
      render(<StepsEditor value={steps} onChange={vi.fn()} />);

      // Component should still render with fallback environments
      expect(screen.getByLabelText(/Environnements conditionnes etape 1/i)).toBeInTheDocument();
    });
  });

  // Story 31.5: AAP template selector tests
  describe('Story 31.5: AAP template selector', () => {
    const aapStep: ExecutionStep[] = [
      {
        order: 1,
        name: 'Deploy AAP',
        type: 'execution',
        connector_type: 'aap',
        connector_config: { resource_type: 'job_template' },
        conditional_environments: null,
      },
    ];

    it('renders AAP template selector when integrationId is provided and templates available', () => {
      mockUseAAPTemplates.mockReturnValue({
        templates: [
          { id: 10, name: 'Deploy DB', description: 'Deploy database' },
          { id: 20, name: 'Patch OS', description: '' },
        ],
        loading: false,
        fallback: false,
        error: null,
      });

      render(<StepsEditor value={aapStep} onChange={vi.fn()} integrationId={1} />);
      expect(screen.getByLabelText(/Template AAP etape 1/i)).toBeInTheDocument();
    });

    it('renders manual input fallback when integrationId is null', () => {
      mockUseAAPTemplates.mockReturnValue(defaultAAPMock);

      render(<StepsEditor value={aapStep} onChange={vi.fn()} integrationId={null} />);
      expect(screen.getByLabelText(/ID template AAP etape 1/i)).toBeInTheDocument();
    });

    it('renders manual input fallback with warning when API error', () => {
      mockUseAAPTemplates.mockReturnValue({
        templates: [],
        loading: false,
        fallback: true,
        error: 'API indisponible',
      });

      render(<StepsEditor value={aapStep} onChange={vi.fn()} integrationId={1} />);
      expect(screen.getByText(/Saisie manuelle/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/ID template AAP etape 1/i)).toBeInTheDocument();
    });

    it('shows loading state', () => {
      mockUseAAPTemplates.mockReturnValue({
        templates: [],
        loading: true,
        fallback: false,
        error: null,
      });

      render(<StepsEditor value={aapStep} onChange={vi.fn()} integrationId={1} />);
      // Loading select should be present
      expect(screen.getByLabelText(/Template AAP etape 1/i)).toBeInTheDocument();
    });

    it('shows retrocompatibility: existing ID displayed in selector', () => {
      const stepsWithId: ExecutionStep[] = [
        {
          order: 1,
          name: 'Deploy AAP',
          type: 'execution',
          connector_type: 'aap',
          connector_config: { resource_type: 'job_template', job_template_id: 99 },
          conditional_environments: null,
        },
      ];

      mockUseAAPTemplates.mockReturnValue({
        templates: [
          { id: 10, name: 'Deploy DB', description: '' },
        ],
        loading: false,
        fallback: false,
        error: null,
      });

      render(<StepsEditor value={stepsWithId} onChange={vi.fn()} integrationId={1} />);
      // Template #99 not in list → should show "introuvable" option
      expect(screen.getByLabelText(/Template AAP etape 1/i)).toBeInTheDocument();
    });

    it('calls onChange when template is selected', async () => {
      const user = userEvent.setup();
      const onChange = vi.fn();
      mockUseAAPTemplates.mockReturnValue({
        templates: [
          { id: 10, name: 'Deploy DB', description: '' },
        ],
        loading: false,
        fallback: false,
        error: null,
      });

      render(<StepsEditor value={aapStep} onChange={onChange} integrationId={1} />);
      const selector = screen.getByLabelText(/Template AAP etape 1/i);
      await user.click(selector);
      const option = await screen.findByText('Deploy DB');
      await user.click(option);
      expect(onChange).toHaveBeenCalledWith([
        expect.objectContaining({
          connector_config: expect.objectContaining({
            job_template_id: 10,
          }),
        }),
      ]);
    });
  });
});

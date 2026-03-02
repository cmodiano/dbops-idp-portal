/**
 * Unit tests for RemediationRulesEditor (Story 9.1, 9.3 + Story 21.4).
 * Tests: add rule, remove rule, validation, auto_trigger constraints,
 * dynamic environments from useEnvironments hook, case-insensitive prod warning.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { RemediationRulesEditor, type RemediationRuleDefinition } from './RemediationRulesEditor';
import { useEnvironments } from '../../hooks/useEnvironments';

// Mock catalog service
vi.mock('../../services/catalog_service', () => ({
  fetchCatalogActions: vi.fn(() =>
    Promise.resolve([
      { id: 10, name: 'Fix Database', engine: 'ansible' },
      { id: 20, name: 'Restart Service', engine: 'rundeck' },
      { id: 30, name: 'Clear Cache', engine: 'custom' },
    ])
  ),
}));

vi.mock('../../hooks/useEnvironments', () => ({
  useEnvironments: vi.fn(),
}));

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

describe('RemediationRulesEditor', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUseEnvironments.mockReturnValue(defaultEnvMock);
  });

  describe('empty state', () => {
    it('renders empty state message when no rules', () => {
      render(<RemediationRulesEditor value={[]} onChange={vi.fn()} />);
      expect(screen.getByText(/Aucune règle de remédiation/i)).toBeInTheDocument();
    });

    it('renders add button', () => {
      render(<RemediationRulesEditor value={[]} onChange={vi.fn()} />);
      expect(
        screen.getByRole('button', { name: /Ajouter une règle de remédiation/i })
      ).toBeInTheDocument();
    });
  });

  describe('add rule', () => {
    it('calls onChange with new rule using dynamic environments', async () => {
      const user = userEvent.setup();
      const onChange = vi.fn();
      render(<RemediationRulesEditor value={[]} onChange={onChange} />);

      await user.click(screen.getByRole('button', { name: /Ajouter une règle/i }));

      expect(onChange).toHaveBeenCalledTimes(1);
      const newValue = onChange.mock.calls[0][0] as RemediationRuleDefinition[];
      expect(newValue).toHaveLength(1);
      expect(newValue[0]).toMatchObject({
        error_pattern: '',
        target_action_id: 0,
        environments: ['dev', 'staging', 'prod'],
        auto_trigger: false,
        risk_level: 'medium',
      });
      expect(newValue[0].id).toBeDefined();
    });
  });

  describe('display rules', () => {
    it('renders rule cards with correct data', async () => {
      const rules: RemediationRuleDefinition[] = [
        {
          id: '1',
          error_pattern: 'ORA-\\d+',
          target_action_id: 10,
          environments: ['dev'],
          auto_trigger: false,
          risk_level: 'low',
        },
        {
          id: '2',
          error_pattern: 'timeout',
          target_action_id: 20,
          environments: ['prod'],
          auto_trigger: true,
          risk_level: 'medium',
        },
      ];
      render(<RemediationRulesEditor value={rules} onChange={vi.fn()} />);

      expect(screen.getByText('Règle 1')).toBeInTheDocument();
      expect(screen.getByText('Règle 2')).toBeInTheDocument();
      // Risk level tags
      expect(screen.getByText('low')).toBeInTheDocument();
      expect(screen.getByText('medium')).toBeInTheDocument();
    });

    it('shows Auto tag for auto_trigger rules', () => {
      const rules: RemediationRuleDefinition[] = [
        {
          id: '1',
          error_pattern: 'error',
          target_action_id: 10,
          environments: ['dev'],
          auto_trigger: true,
          risk_level: 'low',
        },
      ];
      render(<RemediationRulesEditor value={rules} onChange={vi.fn()} />);

      expect(screen.getByText('Auto')).toBeInTheDocument();
    });
  });

  describe('remove rule', () => {
    it('calls onChange without removed rule when delete clicked', async () => {
      const user = userEvent.setup();
      const onChange = vi.fn();
      const rules: RemediationRuleDefinition[] = [
        {
          id: '1',
          error_pattern: 'error1',
          target_action_id: 10,
          environments: ['dev'],
          auto_trigger: false,
          risk_level: 'low',
        },
        {
          id: '2',
          error_pattern: 'error2',
          target_action_id: 20,
          environments: ['prod'],
          auto_trigger: false,
          risk_level: 'high',
        },
      ];
      render(<RemediationRulesEditor value={rules} onChange={onChange} />);

      const deleteButtons = screen.getAllByRole('button', { name: /Supprimer règle/i });
      await user.click(deleteButtons[0]);

      expect(onChange).toHaveBeenCalledTimes(1);
      const newValue = onChange.mock.calls[0][0] as RemediationRuleDefinition[];
      expect(newValue).toHaveLength(1);
      expect(newValue[0].error_pattern).toBe('error2');
    });
  });

  describe('validation', () => {
    it('shows error for empty error_pattern', () => {
      const rules: RemediationRuleDefinition[] = [
        {
          id: '1',
          error_pattern: '',
          target_action_id: 10,
          environments: ['dev'],
          auto_trigger: false,
          risk_level: 'low',
        },
      ];
      render(<RemediationRulesEditor value={rules} onChange={vi.fn()} />);

      expect(screen.getByText(/Pattern requis/i)).toBeInTheDocument();
    });

    it('shows error for invalid regex pattern', () => {
      const rules: RemediationRuleDefinition[] = [
        {
          id: '1',
          error_pattern: '[invalid(regex',
          target_action_id: 10,
          environments: ['dev'],
          auto_trigger: false,
          risk_level: 'low',
        },
      ];
      render(<RemediationRulesEditor value={rules} onChange={vi.fn()} />);

      expect(screen.getByText(/Pattern regex invalide/i)).toBeInTheDocument();
    });

    it('shows error for missing target_action_id', () => {
      const rules: RemediationRuleDefinition[] = [
        {
          id: '1',
          error_pattern: 'error',
          target_action_id: 0,
          environments: ['dev'],
          auto_trigger: false,
          risk_level: 'low',
        },
      ];
      render(<RemediationRulesEditor value={rules} onChange={vi.fn()} />);

      expect(screen.getByText(/Action cible requise/i)).toBeInTheDocument();
    });

    it('shows error for empty environments', () => {
      const rules: RemediationRuleDefinition[] = [
        {
          id: '1',
          error_pattern: 'error',
          target_action_id: 10,
          environments: [],
          auto_trigger: false,
          risk_level: 'low',
        },
      ];
      render(<RemediationRulesEditor value={rules} onChange={vi.fn()} />);

      expect(screen.getByText(/Au moins un environnement requis/i)).toBeInTheDocument();
    });
  });

  // Story 9.3: Auto-trigger constraints (AC4)
  describe('Story 9.3 auto-trigger constraints', () => {
    it('disables auto_trigger switch when risk_level is not low', () => {
      const rules: RemediationRuleDefinition[] = [
        {
          id: '1',
          error_pattern: 'error',
          target_action_id: 10,
          environments: ['dev'],
          auto_trigger: false,
          risk_level: 'medium',
        },
      ];
      render(<RemediationRulesEditor value={rules} onChange={vi.fn()} />);

      const autoSwitch = screen.getByRole('switch', { name: /Déclenchement auto règle 1/i });
      expect(autoSwitch).toBeDisabled();
    });

    it('enables auto_trigger switch when risk_level is low', () => {
      const rules: RemediationRuleDefinition[] = [
        {
          id: '1',
          error_pattern: 'error',
          target_action_id: 10,
          environments: ['dev'],
          auto_trigger: false,
          risk_level: 'low',
        },
      ];
      render(<RemediationRulesEditor value={rules} onChange={vi.fn()} />);

      const autoSwitch = screen.getByRole('switch', { name: /Déclenchement auto règle 1/i });
      expect(autoSwitch).not.toBeDisabled();
    });

    it('auto-disables auto_trigger when risk_level changes from low to medium', async () => {
      const user = userEvent.setup();
      const onChange = vi.fn();
      const rules: RemediationRuleDefinition[] = [
        {
          id: '1',
          error_pattern: 'error',
          target_action_id: 10,
          environments: ['dev'],
          auto_trigger: true,
          risk_level: 'low',
        },
      ];
      render(<RemediationRulesEditor value={rules} onChange={onChange} />);

      // Change risk level to medium
      const riskSelect = screen.getByRole('combobox', { name: /Niveau de risque règle 1/i });
      await user.click(riskSelect);
      await user.click(screen.getByText('Moyen'));

      expect(onChange).toHaveBeenCalled();
      const lastCall = onChange.mock.calls[onChange.mock.calls.length - 1][0] as RemediationRuleDefinition[];
      expect(lastCall[0].risk_level).toBe('medium');
      expect(lastCall[0].auto_trigger).toBe(false);
    });

    it('shows warning when auto_trigger=true and prod environment is selected', () => {
      const rules: RemediationRuleDefinition[] = [
        {
          id: '1',
          error_pattern: 'error',
          target_action_id: 10,
          environments: ['dev', 'prod'],
          auto_trigger: true,
          risk_level: 'low',
        },
      ];
      render(<RemediationRulesEditor value={rules} onChange={vi.fn()} />);

      expect(screen.getByText(/Auto-déclenchement INTERDIT en Production/i)).toBeInTheDocument();
    });

    it('does not show prod warning when auto_trigger=false', () => {
      const rules: RemediationRuleDefinition[] = [
        {
          id: '1',
          error_pattern: 'error',
          target_action_id: 10,
          environments: ['dev', 'prod'],
          auto_trigger: false,
          risk_level: 'low',
        },
      ];
      render(<RemediationRulesEditor value={rules} onChange={vi.fn()} />);

      expect(screen.queryByText(/Auto-déclenchement INTERDIT en Production/i)).not.toBeInTheDocument();
    });

    it('does not show prod warning when prod is not in environments', () => {
      const rules: RemediationRuleDefinition[] = [
        {
          id: '1',
          error_pattern: 'error',
          target_action_id: 10,
          environments: ['dev', 'staging'],
          auto_trigger: true,
          risk_level: 'low',
        },
      ];
      render(<RemediationRulesEditor value={rules} onChange={vi.fn()} />);

      expect(screen.queryByText(/Auto-déclenchement INTERDIT en Production/i)).not.toBeInTheDocument();
    });

    it('shows tooltip explaining auto_trigger disabled for non-low risk', async () => {
      const rules: RemediationRuleDefinition[] = [
        {
          id: '1',
          error_pattern: 'error',
          target_action_id: 10,
          environments: ['dev'],
          auto_trigger: false,
          risk_level: 'high',
        },
      ];
      render(<RemediationRulesEditor value={rules} onChange={vi.fn()} />);

      // The tooltip should indicate that auto-trigger is only for low risk
      const infoIcons = screen.getAllByRole('img', { hidden: true });
      expect(infoIcons.length).toBeGreaterThan(0);
    });
  });

  describe('action dropdown', () => {
    it('loads actions and displays them in dropdown', async () => {
      const user = userEvent.setup();
      const rules: RemediationRuleDefinition[] = [
        {
          id: '1',
          error_pattern: 'error',
          target_action_id: 0,
          environments: ['dev'],
          auto_trigger: false,
          risk_level: 'low',
        },
      ];
      render(<RemediationRulesEditor value={rules} onChange={vi.fn()} />);

      const actionSelect = screen.getByRole('combobox', { name: /Action cible règle 1/i });
      await user.click(actionSelect);

      await waitFor(() => {
        expect(screen.getByText(/Fix Database/)).toBeInTheDocument();
        expect(screen.getByText(/Restart Service/)).toBeInTheDocument();
      });
    });

    it('excludes current action from dropdown when currentActionId provided', async () => {
      const user = userEvent.setup();
      const rules: RemediationRuleDefinition[] = [
        {
          id: '1',
          error_pattern: 'error',
          target_action_id: 0,
          environments: ['dev'],
          auto_trigger: false,
          risk_level: 'low',
        },
      ];
      render(
        <RemediationRulesEditor value={rules} onChange={vi.fn()} currentActionId={10} />
      );

      const actionSelect = screen.getByRole('combobox', { name: /Action cible règle 1/i });
      await user.click(actionSelect);

      await waitFor(() => {
        // Fix Database (id=10) should be excluded
        expect(screen.queryByText(/Fix Database/)).not.toBeInTheDocument();
        expect(screen.getByText(/Restart Service/)).toBeInTheDocument();
      });
    });
  });

  // Story 21.4 tests
  describe('Story 21.4: dynamic environments', () => {
    it('displays dynamic environment options in multi-select', async () => {
      const user = userEvent.setup();
      mockUseEnvironments.mockReturnValue({
        environments: ['dev', 'qa'],
        environmentOptions: [
          { value: 'dev', label: 'Développement' },
          { value: 'qa', label: 'Qa' },
        ],
        loading: false,
        error: null,
      });

      const rules: RemediationRuleDefinition[] = [
        {
          id: '1',
          error_pattern: 'error',
          target_action_id: 10,
          environments: [],
          auto_trigger: false,
          risk_level: 'low',
        },
      ];
      render(<RemediationRulesEditor value={rules} onChange={vi.fn()} />);

      const envSelect = screen.getByRole('combobox', { name: /Environnements règle 1/i });
      await user.click(envSelect);

      expect(screen.getByText('Développement')).toBeInTheDocument();
      expect(screen.getByText('Qa')).toBeInTheDocument();
    });

    it('disables environment select when loading', () => {
      mockUseEnvironments.mockReturnValue({
        ...defaultEnvMock,
        loading: true,
      });

      const rules: RemediationRuleDefinition[] = [
        {
          id: '1',
          error_pattern: 'error',
          target_action_id: 10,
          environments: ['dev'],
          auto_trigger: false,
          risk_level: 'low',
        },
      ];
      render(<RemediationRulesEditor value={rules} onChange={vi.fn()} />);

      const envSelect = screen.getByRole('combobox', { name: /Environnements règle 1/i });
      expect(envSelect.closest('.ant-select-disabled')).toBeTruthy();
    });

    it('shows warning for PROD case-insensitive (uppercase)', () => {
      const rules: RemediationRuleDefinition[] = [
        {
          id: '1',
          error_pattern: 'error',
          target_action_id: 10,
          environments: ['PROD'],
          auto_trigger: true,
          risk_level: 'low',
        },
      ];
      render(<RemediationRulesEditor value={rules} onChange={vi.fn()} />);

      expect(screen.getByText(/Auto-déclenchement INTERDIT en Production/i)).toBeInTheDocument();
    });

    it('shows warning for Prod case-insensitive (mixed case)', () => {
      const rules: RemediationRuleDefinition[] = [
        {
          id: '1',
          error_pattern: 'error',
          target_action_id: 10,
          environments: ['Prod'],
          auto_trigger: true,
          risk_level: 'low',
        },
      ];
      render(<RemediationRulesEditor value={rules} onChange={vi.fn()} />);

      expect(screen.getByText(/Auto-déclenchement INTERDIT en Production/i)).toBeInTheDocument();
    });

    it('no warning when environments contain dev and staging only', () => {
      const rules: RemediationRuleDefinition[] = [
        {
          id: '1',
          error_pattern: 'error',
          target_action_id: 10,
          environments: ['dev', 'staging'],
          auto_trigger: true,
          risk_level: 'low',
        },
      ];
      render(<RemediationRulesEditor value={rules} onChange={vi.fn()} />);

      expect(screen.queryByText(/Auto-déclenchement INTERDIT en Production/i)).not.toBeInTheDocument();
    });

    it('validation with non-standard environments works', () => {
      mockUseEnvironments.mockReturnValue({
        environments: ['dev', 'lab', 'qa'],
        environmentOptions: [
          { value: 'dev', label: 'Développement' },
          { value: 'lab', label: 'Lab' },
          { value: 'qa', label: 'Qa' },
        ],
        loading: false,
        error: null,
      });

      const rules: RemediationRuleDefinition[] = [
        {
          id: '1',
          error_pattern: 'error',
          target_action_id: 10,
          environments: ['lab', 'qa'],
          auto_trigger: false,
          risk_level: 'low',
        },
      ];
      render(<RemediationRulesEditor value={rules} onChange={vi.fn()} />);

      // No validation error for non-standard envs
      expect(screen.queryByText(/Au moins un environnement requis/i)).not.toBeInTheDocument();
    });

    it('new rule uses dynamic environments as default', async () => {
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

      const onChange = vi.fn();
      render(<RemediationRulesEditor value={[]} onChange={onChange} />);

      await user.click(screen.getByRole('button', { name: /Ajouter une règle/i }));

      expect(onChange).toHaveBeenCalledTimes(1);
      const newValue = onChange.mock.calls[0][0] as RemediationRuleDefinition[];
      expect(newValue[0].environments).toEqual(['dev', 'lab']);
    });
  });
});

// ─── Coverage extras ──────────────────────────────────────────────────────────
describe('RemediationRulesEditor — coverage extras', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUseEnvironments.mockReturnValue(defaultEnvMock);
  });

  it('updates error_pattern via Input onChange', async () => {
    const onChange = vi.fn();
    const { fireEvent: fe } = await import('@testing-library/react');
    const rules: RemediationRuleDefinition[] = [
      {
        id: '1',
        error_pattern: '',
        target_action_id: 10,
        environments: ['dev'],
        auto_trigger: false,
        risk_level: 'low',
      },
    ];
    render(<RemediationRulesEditor value={rules} onChange={onChange} />);

    const patternInput = screen.getByRole('textbox', { name: /Pattern d'erreur règle 1/i });
    fe.change(patternInput, { target: { value: 'ORA-123' } });

    expect(onChange).toHaveBeenCalled();
    const lastCall = onChange.mock.calls[onChange.mock.calls.length - 1][0] as RemediationRuleDefinition[];
    expect(lastCall[0].error_pattern).toBe('ORA-123');
  });

  it('updates target_action_id via Select onChange', async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    const rules: RemediationRuleDefinition[] = [
      {
        id: '1',
        error_pattern: 'error',
        target_action_id: 0,
        environments: ['dev'],
        auto_trigger: false,
        risk_level: 'low',
      },
    ];
    render(<RemediationRulesEditor value={rules} onChange={onChange} />);

    const actionSelect = screen.getByRole('combobox', { name: /Action cible règle 1/i });
    await user.click(actionSelect);

    await waitFor(() => {
      expect(screen.getByText(/Fix Database/)).toBeInTheDocument();
    });

    await user.click(screen.getByText(/Fix Database/));

    expect(onChange).toHaveBeenCalled();
    const lastCall = onChange.mock.calls[onChange.mock.calls.length - 1][0] as RemediationRuleDefinition[];
    expect(lastCall[0].target_action_id).toBe(10);
  });

  it('updates environments via Select onChange', async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    const rules: RemediationRuleDefinition[] = [
      {
        id: '1',
        error_pattern: 'error',
        target_action_id: 10,
        environments: ['dev'],
        auto_trigger: false,
        risk_level: 'low',
      },
    ];
    render(<RemediationRulesEditor value={rules} onChange={onChange} />);

    const envSelect = screen.getByRole('combobox', { name: /Environnements règle 1/i });
    await user.click(envSelect);

    await waitFor(() => {
      expect(screen.getByText('Staging')).toBeInTheDocument();
    });

    await user.click(screen.getByText('Staging'));

    expect(onChange).toHaveBeenCalled();
    const lastCall = onChange.mock.calls[onChange.mock.calls.length - 1][0] as RemediationRuleDefinition[];
    expect(lastCall[0].environments).toContain('staging');
  });

  it('updates auto_trigger Switch onChange', async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    const rules: RemediationRuleDefinition[] = [
      {
        id: '1',
        error_pattern: 'error',
        target_action_id: 10,
        environments: ['dev'],
        auto_trigger: false,
        risk_level: 'low',
      },
    ];
    render(<RemediationRulesEditor value={rules} onChange={onChange} />);

    const autoSwitch = screen.getByRole('switch', { name: /Déclenchement auto règle 1/i });
    await user.click(autoSwitch);

    expect(onChange).toHaveBeenCalled();
    const lastCall = onChange.mock.calls[onChange.mock.calls.length - 1][0] as RemediationRuleDefinition[];
    expect(lastCall[0].auto_trigger).toBe(true);
  });

  it('filterOption in action Select works with partial match', async () => {
    const user = userEvent.setup();
    const rules: RemediationRuleDefinition[] = [
      {
        id: '1',
        error_pattern: 'error',
        target_action_id: 0,
        environments: ['dev'],
        auto_trigger: false,
        risk_level: 'low',
      },
    ];
    render(<RemediationRulesEditor value={rules} onChange={vi.fn()} />);

    const actionSelect = screen.getByRole('combobox', { name: /Action cible règle 1/i });
    await user.click(actionSelect);
    await user.type(actionSelect, 'fix');

    await waitFor(() => {
      expect(screen.getByText(/Fix Database/)).toBeInTheDocument();
    });
    // "Restart Service" should be filtered out
    expect(screen.queryByText(/Restart Service/)).not.toBeInTheDocument();
  });
});

/**
 * Unit tests for ImpactRulesEditor (Story 2.18, Task 4.1 + Story 21.4).
 * Tests: add rule, remove rule, environment unique validation, level preview,
 * dynamic environments from useEnvironments hook.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ImpactRulesEditor } from './ImpactRulesEditor';
import type { ImpactRuleDefinition } from '../../types/api';
import { useEnvironments } from '../../hooks/useEnvironments';

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

describe('ImpactRulesEditor', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUseEnvironments.mockReturnValue(defaultEnvMock);
  });

  describe('empty state', () => {
    it('renders empty state message when no rules', () => {
      render(<ImpactRulesEditor value={[]} onChange={vi.fn()} />);
      expect(screen.getByText(/aucune regle d'impact/i)).toBeInTheDocument();
    });

    it('renders add button', () => {
      render(<ImpactRulesEditor value={[]} onChange={vi.fn()} />);
      expect(screen.getByRole('button', { name: /ajouter une regle/i })).toBeInTheDocument();
    });
  });

  describe('add rule', () => {
    it('calls onChange with new rule when add button clicked', async () => {
      const user = userEvent.setup();
      const onChange = vi.fn();
      render(<ImpactRulesEditor value={[]} onChange={onChange} />);

      await user.click(screen.getByRole('button', { name: /ajouter une regle/i }));

      expect(onChange).toHaveBeenCalledTimes(1);
      const newValue = onChange.mock.calls[0][0] as ImpactRuleDefinition[];
      expect(newValue).toHaveLength(1);
      expect(newValue[0]).toMatchObject({
        environment: '',
        level: 'low',
        criteria: null,
      });
      expect(newValue[0].id).toBeDefined();
    });
  });

  describe('display rules', () => {
    it('renders rule cards with correct data', () => {
      const rules: ImpactRuleDefinition[] = [
        { id: '1', environment: 'dev', level: 'low', criteria: 'Dev env' },
        { id: '2', environment: 'prod', level: 'high', criteria: 'Prod env' },
      ];
      render(<ImpactRulesEditor value={rules} onChange={vi.fn()} />);

      expect(screen.getByText('Regle 1')).toBeInTheDocument();
      expect(screen.getByText('Regle 2')).toBeInTheDocument();
      // ImpactIndicator renders labels
      expect(screen.getByText('Faible')).toBeInTheDocument();
      expect(screen.getByText('Élevé')).toBeInTheDocument();
    });
  });

  describe('remove rule', () => {
    it('calls onChange without removed rule when delete clicked', async () => {
      const user = userEvent.setup();
      const onChange = vi.fn();
      const rules: ImpactRuleDefinition[] = [
        { id: '1', environment: 'dev', level: 'low', criteria: null },
        { id: '2', environment: 'prod', level: 'high', criteria: null },
      ];
      render(<ImpactRulesEditor value={rules} onChange={onChange} />);

      const deleteButtons = screen.getAllByRole('button', { name: /supprimer regle/i });
      await user.click(deleteButtons[0]);

      expect(onChange).toHaveBeenCalledTimes(1);
      const newValue = onChange.mock.calls[0][0] as ImpactRuleDefinition[];
      expect(newValue).toHaveLength(1);
      expect(newValue[0].environment).toBe('prod');
    });
  });

  describe('edit rule', () => {
    it('calls onChange when environment changed', async () => {
      const user = userEvent.setup();
      const onChange = vi.fn();
      const rules: ImpactRuleDefinition[] = [
        { id: '1', environment: 'dev', level: 'low', criteria: null },
      ];
      render(<ImpactRulesEditor value={rules} onChange={onChange} />);

      // Open environment select and change value
      const envSelect = screen.getByRole('combobox', { name: /environnement regle 1/i });
      await user.click(envSelect);
      // Click the Staging option from dropdown
      const stagingOptions = screen.getAllByText('Staging');
      await user.click(stagingOptions[stagingOptions.length - 1]);

      expect(onChange).toHaveBeenCalled();
      const lastCall = onChange.mock.calls[onChange.mock.calls.length - 1][0] as ImpactRuleDefinition[];
      expect(lastCall[0].environment).toBe('staging');
    });

    it('calls onChange when level changed', async () => {
      const user = userEvent.setup();
      const onChange = vi.fn();
      const rules: ImpactRuleDefinition[] = [
        { id: '1', environment: 'dev', level: 'low', criteria: null },
      ];
      render(<ImpactRulesEditor value={rules} onChange={onChange} />);

      const levelSelect = screen.getByRole('combobox', { name: /niveau d'impact regle 1/i });
      await user.click(levelSelect);
      await user.click(screen.getByText('Élevé (rouge)'));

      expect(onChange).toHaveBeenCalled();
      const lastCall = onChange.mock.calls[onChange.mock.calls.length - 1][0] as ImpactRuleDefinition[];
      expect(lastCall[0].level).toBe('high');
    });

    it('calls onChange when criteria changed', async () => {
      const user = userEvent.setup();
      const onChange = vi.fn();
      const rules: ImpactRuleDefinition[] = [
        { id: '1', environment: 'dev', level: 'low', criteria: null },
      ];
      render(<ImpactRulesEditor value={rules} onChange={onChange} />);

      const criteriaInput = screen.getByRole('textbox', { name: /critere regle 1/i });
      await user.type(criteriaInput, 'Test criteria');

      expect(onChange).toHaveBeenCalled();
    });
  });

  describe('validation', () => {
    it('shows error for duplicate environment', () => {
      const rules: ImpactRuleDefinition[] = [
        { id: '1', environment: 'dev', level: 'low', criteria: null },
        { id: '2', environment: 'dev', level: 'high', criteria: null },
      ];
      render(<ImpactRulesEditor value={rules} onChange={vi.fn()} />);

      // Should show duplicate error message
      const errors = screen.getAllByText(/environnement deja utilise/i);
      expect(errors.length).toBeGreaterThan(0);
    });

    it('shows error for empty environment', () => {
      const rules: ImpactRuleDefinition[] = [
        { id: '1', environment: '', level: 'low', criteria: null },
      ];
      render(<ImpactRulesEditor value={rules} onChange={vi.fn()} />);

      expect(screen.getByText(/environnement requis/i)).toBeInTheDocument();
    });

    it('shows error for missing level', () => {
      const rules: ImpactRuleDefinition[] = [
        { id: '1', environment: 'dev', level: '' as never, criteria: null },
      ];
      render(<ImpactRulesEditor value={rules} onChange={vi.fn()} />);

      expect(screen.getByText(/niveau requis/i)).toBeInTheDocument();
    });
  });

  describe('ImpactIndicator preview', () => {
    it('displays correct indicator for each level', () => {
      mockUseEnvironments.mockReturnValue({
        ...defaultEnvMock,
        environments: ['dev', 'staging', 'prod', 'lab'],
        environmentOptions: [
          ...defaultEnvMock.environmentOptions,
          { value: 'lab', label: 'Lab' },
        ],
      });

      const rules: ImpactRuleDefinition[] = [
        { id: '1', environment: 'dev', level: 'low', criteria: null },
        { id: '2', environment: 'staging', level: 'medium', criteria: null },
        { id: '3', environment: 'prod', level: 'high', criteria: null },
        { id: '4', environment: 'lab', level: 'critical', criteria: null },
      ];
      render(<ImpactRulesEditor value={rules} onChange={vi.fn()} />);

      expect(screen.getByText('Faible')).toBeInTheDocument();
      expect(screen.getByText('Moyen')).toBeInTheDocument();
      expect(screen.getByText('Élevé')).toBeInTheDocument();
      expect(screen.getByText('Critique')).toBeInTheDocument();
    });
  });

  // Story 21.4 tests
  describe('Story 21.4: dynamic environments', () => {
    it('displays 4 environment options when hook returns 4 envs', async () => {
      const user = userEvent.setup();
      mockUseEnvironments.mockReturnValue({
        environments: ['dev', 'staging', 'prod', 'lab'],
        environmentOptions: [
          { value: 'dev', label: 'Développement' },
          { value: 'staging', label: 'Staging' },
          { value: 'prod', label: 'Production' },
          { value: 'lab', label: 'Lab' },
        ],
        loading: false,
        error: null,
      });

      const rules: ImpactRuleDefinition[] = [
        { id: '1', environment: '', level: 'low', criteria: null },
      ];
      render(<ImpactRulesEditor value={rules} onChange={vi.fn()} />);

      const envSelect = screen.getByRole('combobox', { name: /environnement regle 1/i });
      await user.click(envSelect);

      expect(screen.getByText('Développement')).toBeInTheDocument();
      expect(screen.getByText('Staging')).toBeInTheDocument();
      expect(screen.getByText('Production')).toBeInTheDocument();
      expect(screen.getByText('Lab')).toBeInTheDocument();
    });

    it('disables select when loading', () => {
      mockUseEnvironments.mockReturnValue({
        ...defaultEnvMock,
        loading: true,
      });

      const rules: ImpactRuleDefinition[] = [
        { id: '1', environment: '', level: 'low', criteria: null },
      ];
      render(<ImpactRulesEditor value={rules} onChange={vi.fn()} />);

      const envSelect = screen.getByRole('combobox', { name: /environnement regle 1/i });
      // Ant Design disabled Select: the wrapper gets ant-select-disabled class
      expect(envSelect.closest('.ant-select-disabled')).toBeTruthy();
    });

    it('renders non-standard environments with labels from hook', async () => {
      const user = userEvent.setup();
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

      const rules: ImpactRuleDefinition[] = [
        { id: '1', environment: '', level: 'low', criteria: null },
      ];
      render(<ImpactRulesEditor value={rules} onChange={vi.fn()} />);

      const envSelect = screen.getByRole('combobox', { name: /environnement regle 1/i });
      await user.click(envSelect);

      expect(screen.getByText('Développement')).toBeInTheDocument();
      expect(screen.getByText('Lab')).toBeInTheDocument();
      expect(screen.getByText('Qa')).toBeInTheDocument();
    });

    it('validates duplicate environment with dynamic envs', () => {
      mockUseEnvironments.mockReturnValue({
        environments: ['dev', 'lab'],
        environmentOptions: [
          { value: 'dev', label: 'Développement' },
          { value: 'lab', label: 'Lab' },
        ],
        loading: false,
        error: null,
      });

      const rules: ImpactRuleDefinition[] = [
        { id: '1', environment: 'lab', level: 'low', criteria: null },
        { id: '2', environment: 'lab', level: 'high', criteria: null },
      ];
      render(<ImpactRulesEditor value={rules} onChange={vi.fn()} />);

      const errors = screen.getAllByText(/environnement deja utilise/i);
      expect(errors.length).toBeGreaterThan(0);
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

      const rules: ImpactRuleDefinition[] = [
        { id: '1', environment: '', level: 'low', criteria: null },
      ];
      render(<ImpactRulesEditor value={rules} onChange={vi.fn()} />);

      // Component should still render with fallback environments
      expect(screen.getByRole('combobox', { name: /environnement regle 1/i })).toBeInTheDocument();
    });
  });
});

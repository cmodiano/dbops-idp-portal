/**
 * Unit tests for ImpactRulesEditor (Story 2.18, Task 4.1).
 * Tests: add rule, remove rule, environment unique validation, level preview.
 */

import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ImpactRulesEditor } from './ImpactRulesEditor';
import type { ImpactRuleDefinition } from '../../types/api';

describe('ImpactRulesEditor', () => {
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
        { id: '1', environment: 'DEV', level: 'low', criteria: 'Dev env' },
        { id: '2', environment: 'PROD', level: 'high', criteria: 'Prod env' },
      ];
      render(<ImpactRulesEditor value={rules} onChange={vi.fn()} />);

      expect(screen.getByText('Regle 1')).toBeInTheDocument();
      expect(screen.getByText('Regle 2')).toBeInTheDocument();
      // ImpactIndicator renders labels
      expect(screen.getByText('Faible')).toBeInTheDocument();
      expect(screen.getByText('Eleve')).toBeInTheDocument();
    });
  });

  describe('remove rule', () => {
    it('calls onChange without removed rule when delete clicked', async () => {
      const user = userEvent.setup();
      const onChange = vi.fn();
      const rules: ImpactRuleDefinition[] = [
        { id: '1', environment: 'DEV', level: 'low', criteria: null },
        { id: '2', environment: 'PROD', level: 'high', criteria: null },
      ];
      render(<ImpactRulesEditor value={rules} onChange={onChange} />);

      const deleteButtons = screen.getAllByRole('button', { name: /supprimer regle/i });
      await user.click(deleteButtons[0]);

      expect(onChange).toHaveBeenCalledTimes(1);
      const newValue = onChange.mock.calls[0][0] as ImpactRuleDefinition[];
      expect(newValue).toHaveLength(1);
      expect(newValue[0].environment).toBe('PROD');
    });
  });

  describe('edit rule', () => {
    it('calls onChange when environment changed', async () => {
      const user = userEvent.setup();
      const onChange = vi.fn();
      const rules: ImpactRuleDefinition[] = [
        { id: '1', environment: 'DEV', level: 'low', criteria: null },
      ];
      render(<ImpactRulesEditor value={rules} onChange={onChange} />);

      // Open environment select and change value
      const envSelect = screen.getByRole('combobox', { name: /environnement regle 1/i });
      await user.click(envSelect);
      // Use getAllByText and click the dropdown option (last one)
      const stagingOptions = screen.getAllByText('STAGING');
      await user.click(stagingOptions[stagingOptions.length - 1]);

      expect(onChange).toHaveBeenCalled();
      const lastCall = onChange.mock.calls[onChange.mock.calls.length - 1][0] as ImpactRuleDefinition[];
      expect(lastCall[0].environment).toBe('STAGING');
    });

    it('calls onChange when level changed', async () => {
      const user = userEvent.setup();
      const onChange = vi.fn();
      const rules: ImpactRuleDefinition[] = [
        { id: '1', environment: 'DEV', level: 'low', criteria: null },
      ];
      render(<ImpactRulesEditor value={rules} onChange={onChange} />);

      const levelSelect = screen.getByRole('combobox', { name: /niveau d'impact regle 1/i });
      await user.click(levelSelect);
      await user.click(screen.getByText('Eleve (rouge)'));

      expect(onChange).toHaveBeenCalled();
      const lastCall = onChange.mock.calls[onChange.mock.calls.length - 1][0] as ImpactRuleDefinition[];
      expect(lastCall[0].level).toBe('high');
    });

    it('calls onChange when criteria changed', async () => {
      const user = userEvent.setup();
      const onChange = vi.fn();
      const rules: ImpactRuleDefinition[] = [
        { id: '1', environment: 'DEV', level: 'low', criteria: null },
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
        { id: '1', environment: 'DEV', level: 'low', criteria: null },
        { id: '2', environment: 'DEV', level: 'high', criteria: null },
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
        { id: '1', environment: 'DEV', level: '' as never, criteria: null },
      ];
      render(<ImpactRulesEditor value={rules} onChange={vi.fn()} />);

      expect(screen.getByText(/niveau requis/i)).toBeInTheDocument();
    });
  });

  describe('ImpactIndicator preview', () => {
    it('displays correct indicator for each level', () => {
      // Note: Using custom environment name for critical level to test all levels
      // In production, only DEV/STAGING/PROD are selectable, but editor renders any loaded data
      const rules: ImpactRuleDefinition[] = [
        { id: '1', environment: 'DEV', level: 'low', criteria: null },
        { id: '2', environment: 'STAGING', level: 'medium', criteria: null },
        { id: '3', environment: 'PROD', level: 'high', criteria: null },
        { id: '4', environment: 'CRITICAL_ENV', level: 'critical', criteria: null },
      ];
      render(<ImpactRulesEditor value={rules} onChange={vi.fn()} />);

      expect(screen.getByText('Faible')).toBeInTheDocument();
      expect(screen.getByText('Moyen')).toBeInTheDocument();
      expect(screen.getByText('Eleve')).toBeInTheDocument();
      expect(screen.getByText('Critique')).toBeInTheDocument();
    });
  });
});

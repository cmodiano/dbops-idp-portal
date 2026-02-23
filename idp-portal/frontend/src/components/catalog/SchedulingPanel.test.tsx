/**
 * Tests for SchedulingPanel (Story 34.14 — SOLID-FE-11).
 *
 * SchedulingPanel est un composant contrôlé (aucun state interne) :
 * toute modification appelle onSchedulingChange.
 */

import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { App } from 'antd';
import dayjs from 'dayjs';
import utc from 'dayjs/plugin/utc';
import { SchedulingPanel } from './SchedulingPanel';

dayjs.extend(utc);
import type { SchedulingPanelProps } from './SchedulingPanel';
import type { SchedulingState } from '../../hooks/useExecutionSubmit';
import type { UseSchedulingValidationReturn } from '../../hooks/useSchedulingValidation';

// Évite de charger le modal d'aide complexe dans les tests unitaires
vi.mock('../shared/CronExpressionHelper', () => ({
  default: ({ open }: { open: boolean }) =>
    open ? <div data-testid="cron-helper-open" /> : null,
}));

const mockValidation: UseSchedulingValidationReturn = {
  validateSchedule: vi.fn(() => ({ isValid: true, error: null })),
  validateCronDebounced: vi.fn(),
  handleCronPresetChange: vi.fn(),
};

const baseScheduling: SchedulingState = {
  isScheduling: true,
  schedulingType: 'one-time',
  scheduledAt: null,
  dailyHour: 2,
  dailyMinute: 0,
  weeklyDayOfWeek: 1,
  weeklyHour: 2,
  weeklyMinute: 0,
  cronExpression: '',
  cronIsValid: null,
  cronError: '',
  cronNextExecutions: [],
  cronValidating: false,
  showCronHelper: false,
};

const defaultProps: SchedulingPanelProps = {
  scheduling: baseScheduling,
  onSchedulingChange: vi.fn(),
  schedulingError: null,
  submitting: false,
  validation: mockValidation,
};

function renderSchedulingPanel(props: Partial<SchedulingPanelProps> = {}) {
  return render(
    <App>
      <SchedulingPanel {...defaultProps} {...props} />
    </App>,
  );
}

describe('SchedulingPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('Rendu initial', () => {
    it('rend sans erreur', () => {
      expect(() => renderSchedulingPanel()).not.toThrow();
    });

    it('affiche le groupe de boutons radio avec les 4 types', () => {
      renderSchedulingPanel();
      expect(screen.getByText('Une seule fois')).toBeInTheDocument();
      expect(screen.getByText('Tous les jours')).toBeInTheDocument();
      expect(screen.getByText('Toutes les semaines')).toBeInTheDocument();
      expect(screen.getByText('Avancé (cron)')).toBeInTheDocument();
    });

    it("affiche le DatePicker quand schedulingType='one-time'", () => {
      renderSchedulingPanel({ scheduling: { ...baseScheduling, schedulingType: 'one-time' } });
      expect(screen.getByLabelText("Date et heure d'exécution planifiée")).toBeInTheDocument();
    });
  });

  describe("Type de planification 'daily'", () => {
    it('affiche les selects heure et minute', () => {
      renderSchedulingPanel({ scheduling: { ...baseScheduling, schedulingType: 'daily' } });
      expect(screen.getByLabelText('Heure')).toBeInTheDocument();
      expect(screen.getByLabelText('Minutes')).toBeInTheDocument();
    });

    it("n'affiche pas le DatePicker", () => {
      renderSchedulingPanel({ scheduling: { ...baseScheduling, schedulingType: 'daily' } });
      expect(screen.queryByLabelText("Date et heure d'exécution planifiée")).not.toBeInTheDocument();
    });
  });

  describe("Type de planification 'weekly'", () => {
    it("affiche les selects jour de la semaine, heure et minute", () => {
      renderSchedulingPanel({ scheduling: { ...baseScheduling, schedulingType: 'weekly' } });
      expect(screen.getByLabelText('Jour de la semaine')).toBeInTheDocument();
      // 2 selects heure + 1 select minute (2 aria-label "Heure" présents pour daily+weekly)
      expect(screen.getAllByLabelText('Heure').length).toBeGreaterThanOrEqual(1);
    });

    it("n'affiche pas le DatePicker", () => {
      renderSchedulingPanel({ scheduling: { ...baseScheduling, schedulingType: 'weekly' } });
      expect(screen.queryByLabelText("Date et heure d'exécution planifiée")).not.toBeInTheDocument();
    });
  });

  describe("Type de planification 'cron'", () => {
    it("affiche l'input d'expression cron", () => {
      renderSchedulingPanel({ scheduling: { ...baseScheduling, schedulingType: 'cron' } });
      expect(screen.getByLabelText('Expression cron')).toBeInTheDocument();
    });

    it('affiche le select des préréglages cron', () => {
      renderSchedulingPanel({ scheduling: { ...baseScheduling, schedulingType: 'cron' } });
      expect(screen.getByLabelText('Préréglages cron')).toBeInTheDocument();
    });

    it("affiche le bouton d'aide cron", () => {
      renderSchedulingPanel({ scheduling: { ...baseScheduling, schedulingType: 'cron' } });
      expect(screen.getByRole('button', { name: /aide/i })).toBeInTheDocument();
    });

    it("appelle onSchedulingChange({showCronHelper:true}) au clic sur Aide", async () => {
      const user = userEvent.setup();
      const onSchedulingChange = vi.fn();
      renderSchedulingPanel({
        scheduling: { ...baseScheduling, schedulingType: 'cron' },
        onSchedulingChange,
      });
      await user.click(screen.getByRole('button', { name: /aide/i }));
      expect(onSchedulingChange).toHaveBeenCalledWith({ showCronHelper: true });
    });

    it("affiche les prochaines exécutions quand cronIsValid=true et cronNextExecutions non vide", () => {
      renderSchedulingPanel({
        scheduling: {
          ...baseScheduling,
          schedulingType: 'cron',
          cronExpression: '0 2 * * 1-5',
          cronIsValid: true,
          // Utiliser des valeurs dayjs pour que la conversion UTC fonctionne
          cronNextExecutions: ['2026-03-02T02:00:00Z', '2026-03-03T02:00:00Z'],
        },
      });
      // Le message de l'Alert est "Prochaines exécutions (UTC)"
      expect(screen.getByText('Prochaines exécutions (UTC)')).toBeInTheDocument();
    });

    it("n'affiche pas les prochaines exécutions quand cronIsValid=false", () => {
      renderSchedulingPanel({
        scheduling: {
          ...baseScheduling,
          schedulingType: 'cron',
          cronIsValid: false,
          cronNextExecutions: ['2026-03-02T02:00:00Z'],
        },
      });
      expect(screen.queryByText('Prochaines exécutions (UTC)')).not.toBeInTheDocument();
    });

    it("affiche le message d'erreur cron quand cronIsValid=false et cronError défini", () => {
      renderSchedulingPanel({
        scheduling: {
          ...baseScheduling,
          schedulingType: 'cron',
          cronIsValid: false,
          cronError: 'Expression cron invalide',
          cronNextExecutions: [],
        },
      });
      expect(screen.getByText('Expression cron invalide')).toBeInTheDocument();
    });

    it("affiche l'icône de chargement quand cronValidating=true", () => {
      renderSchedulingPanel({
        scheduling: {
          ...baseScheduling,
          schedulingType: 'cron',
          cronExpression: '0 2 * * *',
          cronValidating: true,
          cronIsValid: null,
        },
      });
      // L'Input cron doit être rendu (validating state actif)
      const cronInput = screen.getByLabelText('Expression cron');
      expect(cronInput).toBeInTheDocument();
      // Le conteneur de l'input contient le spinner Ant Design (ant-input-suffix)
      const wrapper = cronInput.closest('.ant-input-affix-wrapper');
      expect(wrapper?.querySelector('.anticon-loading')).toBeTruthy();
    });

    it("appelle onSchedulingChange avec la nouvelle expression cron", async () => {
      const user = userEvent.setup();
      const onSchedulingChange = vi.fn();
      renderSchedulingPanel({
        scheduling: { ...baseScheduling, schedulingType: 'cron' },
        onSchedulingChange,
      });
      const cronInput = screen.getByLabelText('Expression cron');
      await user.type(cronInput, '0 2 * * *');
      expect(onSchedulingChange).toHaveBeenCalled();
      expect(onSchedulingChange.mock.calls[0][0]).toMatchObject({ cronExpression: expect.any(String) });
    });
  });

  describe('Changement de type via Radio', () => {
    it("appelle onSchedulingChange quand l'utilisateur choisit 'Tous les jours'", async () => {
      const user = userEvent.setup();
      const onSchedulingChange = vi.fn();
      renderSchedulingPanel({ onSchedulingChange });
      await user.click(screen.getByText('Tous les jours'));
      expect(onSchedulingChange).toHaveBeenCalledWith({ schedulingType: 'daily' });
    });

    it("appelle onSchedulingChange quand l'utilisateur choisit 'Toutes les semaines'", async () => {
      const user = userEvent.setup();
      const onSchedulingChange = vi.fn();
      renderSchedulingPanel({ onSchedulingChange });
      await user.click(screen.getByText('Toutes les semaines'));
      expect(onSchedulingChange).toHaveBeenCalledWith({ schedulingType: 'weekly' });
    });
  });

  describe("Erreur de planification", () => {
    it("affiche l'alerte d'erreur quand schedulingError est défini", () => {
      // Utiliser schedulingType='daily' pour éviter la duplication du texte dans Form.Item help
      renderSchedulingPanel({
        scheduling: { ...baseScheduling, schedulingType: 'daily' },
        schedulingError: 'Erreur de planification détectée',
      });
      expect(screen.getByRole('alert')).toBeInTheDocument();
      expect(screen.getByText('Erreur de planification détectée')).toBeInTheDocument();
    });

    it("n'affiche pas l'alerte quand schedulingError est null", () => {
      renderSchedulingPanel({ schedulingError: null });
      expect(screen.queryByRole('alert')).not.toBeInTheDocument();
    });
  });

  describe('État soumission (submitting=true)', () => {
    it('désactive le groupe Radio quand submitting=true', () => {
      renderSchedulingPanel({ submitting: true });
      // Ant Design Radio.Group disabled rend tous les radios disabled
      const radios = screen.getAllByRole('radio');
      radios.forEach((radio) => expect(radio).toBeDisabled());
    });

    it('les contrôles sont activés quand submitting=false', () => {
      renderSchedulingPanel({ submitting: false });
      const radios = screen.getAllByRole('radio');
      radios.forEach((radio) => expect(radio).not.toBeDisabled());
    });
  });

  describe("Aide cron (CronExpressionHelper)", () => {
    it("n'affiche pas le helper cron quand showCronHelper=false", () => {
      renderSchedulingPanel({
        scheduling: { ...baseScheduling, schedulingType: 'cron', showCronHelper: false },
      });
      expect(screen.queryByTestId('cron-helper-open')).not.toBeInTheDocument();
    });

    it("affiche le helper cron quand showCronHelper=true", () => {
      renderSchedulingPanel({
        scheduling: { ...baseScheduling, schedulingType: 'cron', showCronHelper: true },
      });
      expect(screen.getByTestId('cron-helper-open')).toBeInTheDocument();
    });
  });
});

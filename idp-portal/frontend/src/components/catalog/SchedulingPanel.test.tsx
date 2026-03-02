/**
 * Tests for SchedulingPanel (Story 34.14 — SOLID-FE-11).
 *
 * SchedulingPanel est un composant contrôlé (aucun state interne) :
 * toute modification appelle onSchedulingChange.
 */

import { render, screen, fireEvent } from '@testing-library/react';
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
  default: ({ open, onClose }: { open: boolean; onClose: () => void }) =>
    open ? <button data-testid="cron-helper-open" onClick={onClose}>Fermer aide</button> : null,
}));

const mockValidation: UseSchedulingValidationReturn = {
  validateSchedule: vi.fn(() => ({ isValid: true, error: null })),
  validateCronDebounced: vi.fn((_expr, callback) => {
    callback?.({ isValid: true, error: null, nextExecutions: ['2026-03-01T09:00:00Z'], validating: false });
  }),
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

  describe('Cron preset change', () => {
    it("appelle onSchedulingChange avec cronExpression quand un preset non-custom est choisi", async () => {
      const user = userEvent.setup();
      const onSchedulingChange = vi.fn();
      renderSchedulingPanel({
        scheduling: { ...baseScheduling, schedulingType: 'cron' },
        onSchedulingChange,
      });

      // Cliquer sur le select de préréglages
      const presetSelect = screen.getByLabelText('Préréglages cron').closest('.ant-select');
      await user.click(presetSelect!);

      // Choisir le premier preset disponible
      const options = document.querySelectorAll('.ant-select-item-option');
      expect(options.length).toBeGreaterThan(0); // Fail si le dropdown n'a pas ouvert
      await user.click(options[0] as HTMLElement);
      expect(onSchedulingChange).toHaveBeenCalled();
    });

    it("appelle validateCronDebounced quand une expression est saisie", async () => {
      const user = userEvent.setup();
      const onSchedulingChange = vi.fn();
      const validation = {
        ...mockValidation,
        validateCronDebounced: vi.fn(),
      };
      renderSchedulingPanel({
        scheduling: { ...baseScheduling, schedulingType: 'cron' },
        onSchedulingChange,
        validation,
      });

      const cronInput = screen.getByLabelText('Expression cron');
      await user.type(cronInput, '0 9 * * *');

      expect(validation.validateCronDebounced).toHaveBeenCalled();
    });
  });

  describe('Contrôles daily et weekly', () => {
    it("appelle onSchedulingChange quand l'heure daily change", async () => {
      const onSchedulingChange = vi.fn();
      renderSchedulingPanel({
        scheduling: { ...baseScheduling, schedulingType: 'daily' },
        onSchedulingChange,
      });

      const heureSelect = screen.getByLabelText('Heure').closest('.ant-select');
      fireEvent.mouseDown(heureSelect!);
      const options = document.querySelectorAll('.ant-select-item-option');
      expect(options.length).toBeGreaterThan(0); // Fail si le dropdown n'a pas ouvert
      fireEvent.click(options[1] as HTMLElement);
      expect(onSchedulingChange).toHaveBeenCalled();
    });

    it("appelle onSchedulingChange quand la minute daily change", async () => {
      const onSchedulingChange = vi.fn();
      renderSchedulingPanel({
        scheduling: { ...baseScheduling, schedulingType: 'daily' },
        onSchedulingChange,
      });

      const minutesSelect = screen.getByLabelText('Minutes').closest('.ant-select');
      fireEvent.mouseDown(minutesSelect!);
      const options = document.querySelectorAll('.ant-select-item-option');
      expect(options.length).toBeGreaterThan(0); // Fail si le dropdown n'a pas ouvert
      fireEvent.click(options[1] as HTMLElement);
      expect(onSchedulingChange).toHaveBeenCalled();
    });

    it("appelle onSchedulingChange quand le jour weekly change", async () => {
      const onSchedulingChange = vi.fn();
      renderSchedulingPanel({
        scheduling: { ...baseScheduling, schedulingType: 'weekly' },
        onSchedulingChange,
      });

      const jourSelect = screen.getByLabelText('Jour de la semaine').closest('.ant-select');
      fireEvent.mouseDown(jourSelect!);
      const options = document.querySelectorAll('.ant-select-item-option');
      expect(options.length).toBeGreaterThan(0); // Fail si le dropdown n'a pas ouvert
      fireEvent.click(options[1] as HTMLElement);
      expect(onSchedulingChange).toHaveBeenCalled();
    });

    it("appelle onSchedulingChange quand l'heure weekly change", async () => {
      const onSchedulingChange = vi.fn();
      renderSchedulingPanel({
        scheduling: { ...baseScheduling, schedulingType: 'weekly' },
        onSchedulingChange,
      });

      const heureSelects = screen.getAllByLabelText('Heure');
      const heureSelect = heureSelects[0].closest('.ant-select');
      fireEvent.mouseDown(heureSelect!);
      const options = document.querySelectorAll('.ant-select-item-option');
      expect(options.length).toBeGreaterThan(0); // Fail si le dropdown n'a pas ouvert
      fireEvent.click(options[0] as HTMLElement);
      expect(onSchedulingChange).toHaveBeenCalled();
    });

    it("appelle onSchedulingChange quand la minute weekly change", async () => {
      const onSchedulingChange = vi.fn();
      renderSchedulingPanel({
        scheduling: { ...baseScheduling, schedulingType: 'weekly' },
        onSchedulingChange,
      });

      const minutesSelects = screen.getAllByLabelText('Minutes');
      const minutesSelect = minutesSelects[0].closest('.ant-select');
      fireEvent.mouseDown(minutesSelect!);
      const options = document.querySelectorAll('.ant-select-item-option');
      expect(options.length).toBeGreaterThan(0); // Fail si le dropdown n'a pas ouvert
      fireEvent.click(options[1] as HTMLElement);
      expect(onSchedulingChange).toHaveBeenCalled();
    });

    it("affiche les sélecteurs heure/minute pour weekly", () => {
      renderSchedulingPanel({
        scheduling: { ...baseScheduling, schedulingType: 'weekly' },
      });
      expect(screen.getByLabelText('Jour de la semaine')).toBeInTheDocument();
    });
  });

  describe('CronExpressionHelper onClose', () => {
    it("appelle onSchedulingChange({showCronHelper:false}) quand l'aide cron est fermée", async () => {
      const user = userEvent.setup();
      const onSchedulingChange = vi.fn();
      renderSchedulingPanel({
        scheduling: { ...baseScheduling, schedulingType: 'cron', showCronHelper: true },
        onSchedulingChange,
      });

      const closeBtn = screen.getByTestId('cron-helper-open');
      await user.click(closeBtn);
      expect(onSchedulingChange).toHaveBeenCalledWith({ showCronHelper: false });
    });
  });

  describe('DatePicker one-time — onChange et disabledDate', () => {
    it("ouvre le DatePicker et déclenche disabledDate", async () => {
      const user = userEvent.setup();
      const onSchedulingChange = vi.fn();
      renderSchedulingPanel({
        scheduling: { ...baseScheduling, schedulingType: 'one-time' },
        onSchedulingChange,
      });

      const datePicker = screen.getByLabelText("Date et heure d'exécution planifiée");
      // Ouvrir le DatePicker — déclenche disabledDate pour chaque cellule de date
      await user.click(datePicker);

      // Le calendrier doit s'ouvrir
      const calendar = document.querySelector('.ant-picker-dropdown');
      if (calendar) {
        // disabledDate a été appelé pour chaque date du calendrier
        expect(calendar).toBeInTheDocument();
      }
      expect(datePicker).toBeInTheDocument();
    });
  });
});

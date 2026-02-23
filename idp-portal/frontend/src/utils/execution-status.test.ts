/**
 * Tests for execution-status.ts (Story 35.1 — consolidation STATUS_CONFIG résiduel).
 *
 * Vérifie que les nouveaux exports EXECUTION_STATUS_BADGE_CONFIG et STEP_STATUS_BADGE_CONFIG
 * couvrent tous les statuts attendus avec les bons types Ant Design Badge.
 */

import { describe, it, expect } from 'vitest';
import {
  EXECUTION_STATUS_BADGE_CONFIG,
  STEP_STATUS_BADGE_CONFIG,
  STEP_STATUS_COLOR,
  AUDIT_STATUS_CONFIG,
  type BadgeStatusType,
} from './execution-status';

const VALID_BADGE_STATUSES: BadgeStatusType[] = ['success', 'error', 'warning', 'processing', 'default'];

describe('EXECUTION_STATUS_BADGE_CONFIG', () => {
  const expectedStatuses = [
    'SUBMITTED',
    'RUNNING',
    'COMPLETED',
    'FAILED',
    'CANCELLED',
    'INTEGRATION_ERROR',
    'PENDING_APPROVAL',
    'REJECTED',
  ] as const;

  it("couvre les 8 statuts d'exécution", () => {
    expectedStatuses.forEach((status) => {
      expect(EXECUTION_STATUS_BADGE_CONFIG).toHaveProperty(status);
    });
  });

  it('chaque entrée a un color BadgeStatusType valide', () => {
    expectedStatuses.forEach((status) => {
      const { color } = EXECUTION_STATUS_BADGE_CONFIG[status];
      expect(VALID_BADGE_STATUSES).toContain(color);
    });
  });

  it('chaque entrée a un label non vide', () => {
    expectedStatuses.forEach((status) => {
      const { label } = EXECUTION_STATUS_BADGE_CONFIG[status];
      expect(typeof label).toBe('string');
      expect(label.length).toBeGreaterThan(0);
    });
  });

  it("SUBMITTED → default (pas de couleur d'alerte)", () => {
    expect(EXECUTION_STATUS_BADGE_CONFIG.SUBMITTED.color).toBe('default');
  });

  it('RUNNING → processing (animation en cours)', () => {
    expect(EXECUTION_STATUS_BADGE_CONFIG.RUNNING.color).toBe('processing');
  });

  it('COMPLETED → success', () => {
    expect(EXECUTION_STATUS_BADGE_CONFIG.COMPLETED.color).toBe('success');
  });

  it('FAILED → error', () => {
    expect(EXECUTION_STATUS_BADGE_CONFIG.FAILED.color).toBe('error');
  });

  it('INTEGRATION_ERROR → error', () => {
    expect(EXECUTION_STATUS_BADGE_CONFIG.INTEGRATION_ERROR.color).toBe('error');
  });

  it('PENDING_APPROVAL → warning', () => {
    expect(EXECUTION_STATUS_BADGE_CONFIG.PENDING_APPROVAL.color).toBe('warning');
  });

  it('REJECTED → error', () => {
    expect(EXECUTION_STATUS_BADGE_CONFIG.REJECTED.color).toBe('error');
  });
});

describe('STEP_STATUS_BADGE_CONFIG', () => {
  const expectedStatuses = [
    'PENDING',
    'RUNNING',
    'COMPLETED',
    'FAILED',
    'SKIPPED',
    'CANCELLED',
  ] as const;

  it('couvre les 6 statuts step (dont CANCELLED défensif)', () => {
    expectedStatuses.forEach((status) => {
      expect(STEP_STATUS_BADGE_CONFIG).toHaveProperty(status);
    });
  });

  it('chaque entrée a un color BadgeStatusType valide', () => {
    expectedStatuses.forEach((status) => {
      const { color } = STEP_STATUS_BADGE_CONFIG[status];
      expect(VALID_BADGE_STATUSES).toContain(color);
    });
  });

  it('chaque entrée a un label non vide', () => {
    expectedStatuses.forEach((status) => {
      const { label } = STEP_STATUS_BADGE_CONFIG[status];
      expect(typeof label).toBe('string');
      expect(label.length).toBeGreaterThan(0);
    });
  });

  it('PENDING → default', () => {
    expect(STEP_STATUS_BADGE_CONFIG.PENDING.color).toBe('default');
  });

  it('RUNNING → processing', () => {
    expect(STEP_STATUS_BADGE_CONFIG.RUNNING.color).toBe('processing');
  });

  it('COMPLETED → success', () => {
    expect(STEP_STATUS_BADGE_CONFIG.COMPLETED.color).toBe('success');
  });

  it('FAILED → error', () => {
    expect(STEP_STATUS_BADGE_CONFIG.FAILED.color).toBe('error');
  });

  it("SKIPPED → default (pas d'erreur, juste ignoré)", () => {
    expect(STEP_STATUS_BADGE_CONFIG.SKIPPED.color).toBe('default');
  });

  it('CANCELLED → default', () => {
    expect(STEP_STATUS_BADGE_CONFIG.CANCELLED.color).toBe('default');
  });
});

describe('STEP_STATUS_COLOR (régression — existant)', () => {
  it('contient les couleurs hex pour les 5 statuts step de timeline', () => {
    expect(STEP_STATUS_COLOR.PENDING).toBeTruthy();
    expect(STEP_STATUS_COLOR.RUNNING).toBeTruthy();
    expect(STEP_STATUS_COLOR.COMPLETED).toBeTruthy();
    expect(STEP_STATUS_COLOR.FAILED).toBeTruthy();
    expect(STEP_STATUS_COLOR.SKIPPED).toBeTruthy();
  });

  it('toutes les valeurs sont des couleurs hex valides', () => {
    const hexColorRegex = /^#[0-9A-Fa-f]{3,8}$/;
    Object.values(STEP_STATUS_COLOR).forEach((color) => {
      expect(color).toMatch(hexColorRegex);
    });
  });
});

describe('AUDIT_STATUS_CONFIG (régression — existant)', () => {
  it('contient les 4 statuts audit', () => {
    expect(AUDIT_STATUS_CONFIG).toHaveProperty('success');
    expect(AUDIT_STATUS_CONFIG).toHaveProperty('failed');
    expect(AUDIT_STATUS_CONFIG).toHaveProperty('running');
    expect(AUDIT_STATUS_CONFIG).toHaveProperty('unknown');
  });
});

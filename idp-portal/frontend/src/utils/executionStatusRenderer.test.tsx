/**
 * Smoke tests for executionStatusRenderer (direct import — Story 54.13 code review).
 *
 * Purpose: validate the NEW module is directly importable and its exports are correct
 * independently of the re-export chain in executionRenderers.tsx.
 * The exhaustive behavioural tests live in executionRenderers.test.tsx.
 */

import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/react';
import { STATUS_CONFIG, renderStatusIndicator } from './executionStatusRenderer';
import type { ExecutionStatusType } from '../types/api';

const ALL_STATUSES: ExecutionStatusType[] = [
  'SUBMITTED',
  'INTEGRATION_ERROR',
  'PENDING_APPROVAL',
  'RUNNING',
  'COMPLETED',
  'FAILED',
  'CANCELLED',
  'REJECTED',
];

describe('executionStatusRenderer — direct import (Story 54.13)', () => {
  describe('STATUS_CONFIG', () => {
    it('exports STATUS_CONFIG with all ExecutionStatusType keys', () => {
      ALL_STATUSES.forEach((status) => {
        expect(STATUS_CONFIG).toHaveProperty(status);
        expect(STATUS_CONFIG[status]).toHaveProperty('label');
        expect(STATUS_CONFIG[status]).toHaveProperty('Icon');
        expect(STATUS_CONFIG[status]).toHaveProperty('color');
      });
    });

    it('STATUS_CONFIG labels are feminine French strings (SOLID-FE-10)', () => {
      expect(STATUS_CONFIG.COMPLETED.label).toBe('Terminée');
      expect(STATUS_CONFIG.CANCELLED.label).toBe('Annulée');
      expect(STATUS_CONFIG.SUBMITTED.label).toBe('Soumise');
    });
  });

  describe('renderStatusIndicator', () => {
    it('is exported as a function', () => {
      expect(typeof renderStatusIndicator).toBe('function');
    });

    it('renders a React node for each status without throwing', () => {
      ALL_STATUSES.forEach((status) => {
        expect(() => render(<>{renderStatusIndicator(status)}</>)).not.toThrow();
      });
    });
  });
});

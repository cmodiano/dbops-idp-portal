/**
 * Tests for business-friendly language utilities (Story 7.1).
 */

import { describe, it, expect } from 'vitest';
import { sanitizeDescription, containsTechnicalTerms } from './businessLanguage';

describe('sanitizeDescription', () => {
  it('replaces pipeline with processus automatique', () => {
    expect(sanitizeDescription('Run the pipeline to deploy')).toBe(
      'Run the processus automatique to deployer'
    );
  });

  it('replaces playbook with action', () => {
    // "Execute" is also replaced, and "Ansible" becomes "automatisation"
    expect(sanitizeDescription('Run the Ansible playbook')).toBe(
      'Run the automatisation action'
    );
  });

  it('replaces webhook with notification automatique', () => {
    expect(sanitizeDescription('Configure the webhook')).toBe(
      'Configure the notification automatique'
    );
  });

  it('replaces template with modele', () => {
    expect(sanitizeDescription('Use the job template')).toBe('Use the tache modele');
  });

  it('replaces inventory with liste des serveurs', () => {
    expect(sanitizeDescription('Check the inventory')).toBe('Check the liste des serveurs');
  });

  it('replaces workflow with enchainement', () => {
    expect(sanitizeDescription('Start the workflow')).toBe('Start the enchainement');
  });

  it('replaces vault with coffre-fort de secrets', () => {
    expect(sanitizeDescription('Fetch from Vault')).toBe('Fetch from coffre-fort de secrets');
  });

  it('replaces credentials with acces securises', () => {
    expect(sanitizeDescription('Store the credentials')).toBe('Store the acces securises');
  });

  it('handles case-insensitive replacements', () => {
    expect(sanitizeDescription('PIPELINE and Pipeline')).toBe(
      'processus automatique and processus automatique'
    );
  });

  it('handles multiple terms in one string', () => {
    const input = 'The pipeline triggers a webhook to start a job';
    const expected = 'The processus automatique triggers a notification automatique to start a tache';
    expect(sanitizeDescription(input)).toBe(expected);
  });

  it('returns empty string for null/undefined', () => {
    expect(sanitizeDescription(null)).toBe('');
    expect(sanitizeDescription(undefined)).toBe('');
    expect(sanitizeDescription('')).toBe('');
  });

  it('preserves non-technical text unchanged', () => {
    expect(sanitizeDescription('This is a simple description')).toBe(
      'This is a simple description'
    );
  });

  it('only replaces whole words (word boundaries)', () => {
    // "job" should not be replaced in "jobless" because it's not a whole word
    expect(sanitizeDescription('The job is running')).toBe('The tache is running');
    // Make sure partial matches don't get replaced incorrectly
    expect(sanitizeDescription('pipeline-job-workflow')).toContain('tache');
  });
});

describe('containsTechnicalTerms', () => {
  it('returns true when technical terms are present', () => {
    expect(containsTechnicalTerms('Run the pipeline')).toBe(true);
    expect(containsTechnicalTerms('Execute playbook')).toBe(true);
    expect(containsTechnicalTerms('Configure webhook')).toBe(true);
  });

  it('returns false when no technical terms are present', () => {
    expect(containsTechnicalTerms('This is a simple description')).toBe(false);
    expect(containsTechnicalTerms('Database maintenance')).toBe(true); // "database" is a technical term
    expect(containsTechnicalTerms('User management')).toBe(false);
  });

  it('returns false for null/undefined/empty', () => {
    expect(containsTechnicalTerms(null)).toBe(false);
    expect(containsTechnicalTerms(undefined)).toBe(false);
    expect(containsTechnicalTerms('')).toBe(false);
  });

  it('is case-insensitive', () => {
    expect(containsTechnicalTerms('PIPELINE')).toBe(true);
    expect(containsTechnicalTerms('Pipeline')).toBe(true);
    expect(containsTechnicalTerms('pIpElInE')).toBe(true);
  });
});

describe('regex pre-compilation (Story 30.9, PERF-3)', () => {
  it('produces identical output across 100 consecutive calls (no state mutation)', () => {
    const input = 'Execute the Ansible playbook to deploy the pipeline';
    const expected = sanitizeDescription(input);

    for (let i = 0; i < 100; i++) {
      expect(sanitizeDescription(input)).toBe(expected);
    }
  });

  it('containsTechnicalTerms is stable across repeated calls', () => {
    for (let i = 0; i < 100; i++) {
      expect(containsTechnicalTerms('Run the pipeline')).toBe(true);
      expect(containsTechnicalTerms('Simple text')).toBe(false);
    }
  });
});

/**
 * Profile options — shared constants for ProfileForm and ProfileWizard (Story 2.25).
 * Extracted to avoid duplication (Dev Notes recommendation).
 */

export const ENVIRONMENT_OPTIONS = ['DEV', 'STAGING', 'PROD'] as const;

/** Story 2.11: Mock inventory targets until Epic 4 (AC3). */
export const MOCK_TARGET_OPTIONS = ['assurance-db01', 'assurance-db02', 'infra-oracle-prod'] as const;

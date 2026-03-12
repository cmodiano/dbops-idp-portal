/**
 * Profile options — shared constants for ProfileForm and ProfileWizard (Story 2.25).
 */

/**
 * @deprecated NEW-FE-A: No longer used. ProfileForm and ProfileWizard now fetch real
 * inventory targets via useTargetsPaginated (Epic 4 was delivered). Kept to avoid
 * import errors in any remaining tests; will be removed once test imports are updated.
 */
export const MOCK_TARGET_OPTIONS = ['assurance-db01', 'assurance-db02', 'infra-oracle-prod'] as const;

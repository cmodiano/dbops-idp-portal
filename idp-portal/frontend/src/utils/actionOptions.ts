/**
 * Shared options for action form/wizard (Story 2.1, 2.22).
 * Used by ActionForm and ActionWizard to avoid duplication.
 * Story 2.23: CATEGORY_OPTIONS removed — use tags for categorization.
 * Story 13.7: ENGINE_OPTIONS removed — use useEngines hook to load from REF_ENGINES table.
 */

// ENGINE_OPTIONS removed - use useEngines hook instead (Story 13.7)
// This constant is kept for backward compatibility but should not be used.
// Components should use useEngines() hook to load engines from API.
export const ENGINE_OPTIONS_DEPRECATED: { value: string; label: string }[] = [
  { value: 'Oracle', label: 'Oracle' },
  { value: 'SQL Server', label: 'SQL Server' },
  { value: 'DB2', label: 'DB2' },
];

// Story 31.9: PLATFORM_OPTIONS_DEPRECATED removed — use usePlatformIntegrations hook instead.

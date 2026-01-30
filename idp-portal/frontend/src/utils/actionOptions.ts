/**
 * Shared options for action form/wizard (Story 2.1, 2.22).
 * Used by ActionForm and ActionWizard to avoid duplication.
 * Story 2.23: CATEGORY_OPTIONS removed — use tags for categorization.
 */

import type { ActionEngine, ActionPlatform } from '../types/api';

export const ENGINE_OPTIONS: { value: ActionEngine; label: string }[] = [
  { value: 'Oracle', label: 'Oracle' },
  { value: 'SQL Server', label: 'SQL Server' },
  { value: 'DB2', label: 'DB2' },
];

export const PLATFORM_OPTIONS: { value: ActionPlatform; label: string }[] = [
  { value: 'AAP', label: 'AAP (Ansible Automation Platform)' },
  { value: 'GitHub Actions', label: 'GitHub Actions' },
  { value: 'Azure DevOps', label: 'Azure DevOps' },
  { value: 'Terraform', label: 'Terraform' },
];

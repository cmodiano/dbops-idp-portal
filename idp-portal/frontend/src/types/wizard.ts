/**
 * Wizard types for execution re-launch (Story 17.15).
 */

/**
 * Initial parameters to pre-fill the ExecutionWizard when re-launching an execution.
 * All fields optional — only provided fields will be pre-filled.
 */
export interface WizardInitialParams {
  /** Action ID to pre-select in the wizard. */
  actionId?: number;
  /** Target names to pre-select. */
  targetNames?: string[];
  /** Environment to pre-select. */
  environment?: string;
  /** Dynamic parameters to pre-fill in the form. */
  parameters?: Record<string, unknown>;
}

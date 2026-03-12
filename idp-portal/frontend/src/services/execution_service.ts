/**
 * Execution service (Story 4.1; Story 9.1, 9.2 remediation).
 *
 * Barrel file — re-exports from execution_core, execution_dashboard, execution_inventory.
 * All functions remain available from this module for backward compatibility.
 */

// Core: submit, get, list, approve, cancel, remediation
export {
  buildFilterParams,
  submitExecution,
  getExecution,
  getExecutionSteps,
  getStepLogs,
  listExecutions,
  listPendingApprovals,
  getPendingApprovalsCount,
  approveExecution,
  rejectExecution,
  cancelExecution,
  fetchRemediationSuggestions,
  fetchRemediationContext,
} from './execution_core';
export type {
  ListExecutionsResponse,
  PendingApprovalsResponse,
  PendingApprovalsCountResponse,
  ApproveExecutionResponse,
  RejectExecutionResponse,
} from './execution_core';

// Dashboard: stats, timeseries, tags
export {
  fetchExecutionStats,
  fetchExecutionTimeSeries,
  fetchExecutionTags,
} from './execution_dashboard';

// Inventory: targets, inventory items, schema
export {
  fetchTargetsPaginated,
  fetchInventoryTargets,
  fetchInventoryItems,
  fetchInventorySchema,
} from './execution_inventory';
export type { InventoryTarget, TargetsResponse } from './execution_inventory';

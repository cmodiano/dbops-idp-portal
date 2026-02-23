import type { ExecutionStatusType } from '../types/api';

/** Statuses that indicate an execution is still in progress; list should poll while any of these are present. */
export const RUNNING_STATUSES: ExecutionStatusType[] = [
  'RUNNING',
  'SUBMITTED',
  'PENDING_APPROVAL',
];

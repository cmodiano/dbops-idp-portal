// Central re-export for all API types
// For backward compatibility, import from specific domain files when possible
//
// Recommended import patterns:
//   import type { ActionResponse } from '../types/api/catalog';
//   import type { ExecutionResponse } from '../types/api/executions';
//   import type { ProfileResponse } from '../types/api/profiles';
//
// Barrel import (still supported):
//   import type { ActionResponse, ExecutionResponse } from '../types/api';

// Common types
export * from './common';

// Domain-specific types
export * from './catalog';
export * from './executions';
export * from './profiles';
export * from './integrations';
export * from './audit';
export * from './analytics';
export * from './scheduled';
export * from './inventory';
export * from './remediation';

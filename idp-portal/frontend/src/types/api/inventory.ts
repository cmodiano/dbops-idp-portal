// === Inventory Types (Story 4.1, Task 2) ===

import type { InventorySourceType } from './catalog';

/** Inventory item for dropdowns (Story 4.1, Task 2.1). */
export interface InventoryItem {
  id: string;
  name: string;
  environment: string | null;
  engine_type?: string | null;  // servers (Story 37.5)
  server_ref?: string | null;   // instances (Story 37.5)
  db_ref?: string | null;       // instances (Story 37.5)
}

/**
 * Story 62.5 — Schema of available column concepts per inventory entity type.
 * Matches response of GET /api/v1/inventory/schema/
 */
export type InventorySchema = Record<InventorySourceType, string[]>;

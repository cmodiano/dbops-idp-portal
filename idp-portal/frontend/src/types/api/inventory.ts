// === Inventory Types (Story 4.1, Task 2) ===

/** Inventory item for dropdowns (Story 4.1, Task 2.1). */
export interface InventoryItem {
  id: string;
  name: string;
  environment: string | null;
}

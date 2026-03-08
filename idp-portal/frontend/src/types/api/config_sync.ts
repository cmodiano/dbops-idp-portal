export interface ConfigSyncEntityStatus {
  entity_type: string;
  total: number;
  synced: number;
  diverged: number;
  never_synced: number;
  last_sync_date: string | null;
}

export interface ConfigSyncGlobal {
  total: number;
  synced: number;
  diverged: number;
  never_synced: number;
  last_sync_date: string | null;
}

export interface ConfigSyncStatusResponse {
  data: {
    global: ConfigSyncGlobal;
    entity_types: ConfigSyncEntityStatus[];
  };
}

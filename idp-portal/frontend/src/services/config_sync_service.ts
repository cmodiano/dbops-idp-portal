import { apiFetch } from './api_client';
import type { ConfigSyncStatusResponse } from '../types/api/config_sync';

export async function getConfigSyncStatus(): Promise<ConfigSyncStatusResponse> {
  return apiFetch<ConfigSyncStatusResponse>('/admin/config-sync/status/');
}

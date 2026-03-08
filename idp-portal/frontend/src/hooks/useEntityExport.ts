/**
 * useEntityExport - Hook for exporting a single entity as YAML (Story 64.13).
 *
 * Calls GET /api/v1/admin/<entity>/<id>/export/yaml/ and triggers a browser download.
 * Handles loading state and displays error notification via Ant Design.
 */
import { useState, useCallback } from 'react';
import { App } from 'antd';
import { apiFetchBlob } from '../services/api_client';

export type EntityType = 'actions' | 'integrations' | 'profiles';

export interface UseEntityExportReturn {
  exportYaml: () => Promise<void>;
  loading: boolean;
}

export function useEntityExport(
  entityType: EntityType,
  id: number,
  name: string,
): UseEntityExportReturn {
  const [loading, setLoading] = useState(false);
  const { notification } = App.useApp();

  const exportYaml = useCallback(async () => {
    setLoading(true);
    try {
      const blob = await apiFetchBlob(`/admin/${entityType}/${id}/export/yaml/`);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${entityType}-${name}.yaml`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (err) {
      notification.error({
        message: 'Erreur export YAML',
        description: String(err),
      });
    } finally {
      setLoading(false);
    }
  }, [entityType, id, name, notification]);

  return { exportYaml, loading };
}

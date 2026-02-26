import { useCallback, useEffect, useState } from 'react';

import {
  createApiKey,
  listApiKeys,
  revokeApiKey,
  type ApiKeyListItem,
  type ApiKeyScope,
} from '../services/api_keys_service';

export function useApiKeys() {
  const [keys, setKeys] = useState<ApiKeyListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastCreatedRawKey, setLastCreatedRawKey] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await listApiKeys();
      setKeys(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erreur de chargement des clés API');
      setKeys([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const create = useCallback(async (name: string, scope?: ApiKeyScope) => {
    setSaving(true);
    setError(null);
    try {
      const created = await createApiKey({ name, scope: scope ?? null });
      setLastCreatedRawKey(created.raw_key);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erreur de création de clé API');
      throw err;
    } finally {
      setSaving(false);
    }
  }, [load]);

  const revoke = useCallback(async (id: number) => {
    setSaving(true);
    setError(null);
    try {
      await revokeApiKey(id);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erreur de révocation de clé API');
      throw err;
    } finally {
      setSaving(false);
    }
  }, [load]);

  return {
    keys,
    loading,
    saving,
    error,
    lastCreatedRawKey,
    create,
    revoke,
    clearRawKey: () => setLastCreatedRawKey(null),
  };
}

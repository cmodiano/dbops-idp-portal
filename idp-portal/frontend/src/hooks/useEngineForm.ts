/**
 * useEngineForm — Encapsulation DIP de updateEngine (engines_service) pour EngineForm.
 * Story 54.15 (SOLID-FE-4, AC4): Supprime l'import direct depuis engines_service dans EngineForm.tsx.
 * Hook de mutation uniquement — ne charge pas la liste des moteurs.
 */

import { useState, useCallback } from 'react';
import { updateEngine } from '../services/engines_service';
import type { RefEngine } from '../services/reference_service';

export interface UseEngineFormReturn {
  handleUpdate: (id: number, data: Partial<RefEngine>) => Promise<RefEngine>;
  saving: boolean;
  error: string | null;
}

export function useEngineForm(): UseEngineFormReturn {
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleUpdate = useCallback(async (id: number, data: Partial<RefEngine>): Promise<RefEngine> => {
    setSaving(true);
    setError(null);
    try {
      return await updateEngine(id, data);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Erreur lors de l'enregistrement";
      setError(msg);
      throw err;
    } finally {
      setSaving(false);
    }
  }, []);

  return { handleUpdate, saving, error };
}

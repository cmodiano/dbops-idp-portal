/**
 * useProfileImport — Encapsulation DIP de importProfilesYaml (profiles_service).
 * Story 54.15 (SOLID-FE-4, AC7): Supprime l'import direct depuis profiles_service dans ProfileImportModal.tsx.
 */

import { useState, useCallback } from 'react';
import { importProfilesYaml } from '../services/profiles_service';
import logger from '../services/logger';

export interface UseProfileImportReturn {
  importFile: (file: File) => Promise<{ created: number; updated: number }>;
  importing: boolean;
  error: string | null;
  reset: () => void;
}

export function useProfileImport(): UseProfileImportReturn {
  const [importing, setImporting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const importFile = useCallback(async (file: File): Promise<{ created: number; updated: number }> => {
    setImporting(true);
    setError(null);
    try {
      return await importProfilesYaml(file);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Erreur lors de l'import YAML";
      logger.error('useProfileImport failed', { error: msg });
      setError(msg);
      throw err;
    } finally {
      setImporting(false);
    }
  }, []);

  const reset = useCallback(() => {
    setError(null);
  }, []);

  return { importFile, importing, error, reset };
}

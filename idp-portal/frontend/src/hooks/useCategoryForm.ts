/**
 * useCategoryForm — Encapsulation DIP de createCategory/updateCategory (categories_service).
 * Story 54.15 (SOLID-FE-4, AC2): Supprime les imports directs depuis categories_service dans CategoryForm.tsx.
 */

import { useState, useCallback } from 'react';
import { createCategory, updateCategory } from '../services/categories_service';
import type { RefCategory } from '../types/api';
import logger from '../services/logger';

export interface UseCategoryFormReturn {
  submit: (
    data: { code: string; label: string; display_order: number; is_active: number },
    editId?: number
  ) => Promise<RefCategory>;
  submitting: boolean;
  error: string | null;
}

export function useCategoryForm(): UseCategoryFormReturn {
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = useCallback(
    async (
      data: { code: string; label: string; display_order: number; is_active: number },
      editId?: number
    ): Promise<RefCategory> => {
      setSubmitting(true);
      setError(null);
      try {
        const result = editId
          ? await updateCategory(editId, data)
          : await createCategory(data);
        return result;
      } catch (err) {
        const msg = err instanceof Error ? err.message : "Erreur lors de l'enregistrement";
        logger.error('useCategoryForm submit failed', { error: msg });
        setError(msg);
        throw err;
      } finally {
        setSubmitting(false);
      }
    },
    []
  );

  return { submit, submitting, error };
}

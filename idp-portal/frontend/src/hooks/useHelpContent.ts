import { useState, useEffect } from 'react';
import { getHelpContent, type HelpContent } from '../services/help_service';

interface UseHelpContentReturn {
  content: HelpContent | null;
  loading: boolean;
  error: string | null;
}

/**
 * Hook pour charger le contenu d'aide contextuelle.
 *
 * Note : getHelpContent() ne throw jamais (erreurs silencieuses → objet vide retourné).
 * Le bloc catch ci-dessous est une sécurité défensive en cas d'évolution du contrat du service.
 */
export function useHelpContent(topicId: string): UseHelpContentReturn {
  const [content, setContent] = useState<HelpContent | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      setLoading(true);
      try {
        const data = await getHelpContent(topicId);
        if (!cancelled) {
          setContent(data);
          setError(null);
        }
      } catch (err: unknown) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Erreur');
          setContent(null);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    load();
    return () => {
      cancelled = true;
    };
  }, [topicId]);

  return { content, loading, error };
}

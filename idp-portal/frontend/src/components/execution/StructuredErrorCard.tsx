/**
 * StructuredErrorCard - Gestion d'erreur structurée (Story 4.7, AC2, AC5).
 *
 * Affiche Quoi (étape échouée), Pourquoi (cause), Options (Relancer, Voir logs, Contacter DBA).
 * role="alert", aria-labelledby, focus automatique sur le premier bouton option.
 */

import { useEffect, useRef } from 'react';
import { Button } from 'antd';

const ERROR_COLOR = '#EF4444';

export interface StructuredErrorCardProps {
  /** Ce qui a échoué (étape ou action). */
  quoi: string;
  /** Cause ou message d'erreur. */
  pourquoi: string;
  /** ID de l'étape (pour onViewLogs). */
  stepId?: number;
  /** ID de l'exécution (pour onRetry / contexte). */
  executionId?: number;
  /** Callback Relancer (relance l'exécution ou retour au wizard). */
  onRetry?: () => void;
  /** Callback Voir logs (ouvre panneau logs pour stepId). */
  onViewLogs?: () => void;
  /** Callback Contacter DBA (lien mailto ou page aide). */
  onContact?: () => void;
}

export function StructuredErrorCard({
  quoi,
  pourquoi,
  onRetry,
  onViewLogs,
  onContact,
}: StructuredErrorCardProps) {
  const firstOptionRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    firstOptionRef.current?.focus();
  }, []);

  return (
    <div
      role="alert"
      aria-labelledby="structured-error-quoi-heading structured-error-pourquoi-heading"
      style={{
        padding: 16,
        borderRadius: 8,
        border: `1px solid ${ERROR_COLOR}`,
        backgroundColor: 'rgba(239, 68, 68, 0.06)',
      }}
    >
      <section aria-labelledby="structured-error-quoi-heading" style={{ marginBottom: 12 }}>
        <h3
          id="structured-error-quoi-heading"
          style={{ margin: '0 0 4px 0', fontSize: 14, fontWeight: 600, color: '#374151' }}
        >
          Quoi
        </h3>
        <p style={{ margin: 0, fontSize: 14, color: '#1f2937' }}>{quoi}</p>
      </section>
      <section aria-labelledby="structured-error-pourquoi-heading" style={{ marginBottom: 16 }}>
        <h3
          id="structured-error-pourquoi-heading"
          style={{ margin: '0 0 4px 0', fontSize: 14, fontWeight: 600, color: '#374151' }}
        >
          Pourquoi
        </h3>
        <p style={{ margin: 0, fontSize: 14, color: ERROR_COLOR }}>{pourquoi}</p>
      </section>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
        <Button
          ref={firstOptionRef}
          type="primary"
          danger
          onClick={onRetry}
          disabled={!onRetry}
          style={{ outlineOffset: 2 }}
        >
          Relancer
        </Button>
        <Button onClick={onViewLogs} disabled={!onViewLogs} style={{ outlineOffset: 2 }}>
          Voir logs
        </Button>
        <Button onClick={onContact} disabled={!onContact} style={{ outlineOffset: 2 }}>
          Contacter DBA
        </Button>
      </div>
    </div>
  );
}

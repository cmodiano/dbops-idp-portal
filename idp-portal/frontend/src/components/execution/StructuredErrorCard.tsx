/**
 * StructuredErrorCard - Gestion d'erreur structurée (Story 4.7, AC2, AC5).
 *
 * Affiche Quoi (étape échouée), Pourquoi (cause), Options (Relancer, Voir logs, Contacter DBA).
 * role="alert", aria-labelledby, focus automatique sur le premier bouton option.
 *
 * Story 7.2, AC3: Business variant with simplified labels and sanitized error messages.
 * Story 9.1, AC1, AC3: Display remediation suggestions section when available.
 */

import { useEffect, useRef } from 'react';
import { Button, Tooltip, Space, Skeleton, theme } from 'antd';
import { ToolOutlined } from '@ant-design/icons';
import { sanitizeDescription } from '../../utils/businessLanguage';
import type { RemediationSuggestion } from '../../types/api';

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
  /** Display variant: 'default' for technical users, 'business' for simplified view (Story 7.2, Task 3.1). */
  variant?: 'default' | 'business';
  /** Remediation suggestions (Story 9.1, AC1). */
  remediationSuggestions?: RemediationSuggestion[];
  /** Callback when a remediation suggestion is clicked (Story 9.1, AC1). */
  onSuggestionClick?: (suggestion: RemediationSuggestion) => void;
  /** Loading state for remediation suggestions (Story 9.1, Task 11.4). */
  suggestionsLoading?: boolean;
}

export function StructuredErrorCard({
  quoi,
  pourquoi,
  onRetry,
  onViewLogs,
  onContact,
  variant = 'default',
  remediationSuggestions,
  onSuggestionClick,
  suggestionsLoading,
}: StructuredErrorCardProps) {
  const { token } = theme.useToken();
  const firstOptionRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    firstOptionRef.current?.focus();
  }, []);

  // Story 7.2, Task 3.2: Simplified labels for business variant
  const quoiLabel = variant === 'business' ? 'Qu\'est-ce qui s\'est passe?' : 'Quoi';
  const pourquoiLabel = variant === 'business' ? 'Explication' : 'Pourquoi';

  // Story 7.2, Task 3.3: Apply sanitizeDescription() to error message in business mode
  const displayPourquoi = variant === 'business' ? sanitizeDescription(pourquoi) : pourquoi;

  // Story 9.1, AC1: Check if we have suggestions to display
  const hasSuggestions = remediationSuggestions && remediationSuggestions.length > 0;

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
          style={{ margin: '0 0 4px 0', fontSize: 14, fontWeight: 600, color: token.colorTextSecondary }}
        >
          {quoiLabel}
        </h3>
        <p style={{ margin: 0, fontSize: 14, color: token.colorText }}>{quoi}</p>
      </section>
      <section aria-labelledby="structured-error-pourquoi-heading" style={{ marginBottom: 16 }}>
        <h3
          id="structured-error-pourquoi-heading"
          style={{ margin: '0 0 4px 0', fontSize: 14, fontWeight: 600, color: token.colorTextSecondary }}
        >
          {pourquoiLabel}
        </h3>
        <p style={{ margin: 0, fontSize: 14, color: ERROR_COLOR }}>{displayPourquoi}</p>
      </section>

      {/* Story 9.1, AC1: Display remediation suggestions section when available */}
      {suggestionsLoading && (
        <section style={{ marginBottom: 16 }}>
          <h3 style={{ margin: '0 0 8px 0', fontSize: 14, fontWeight: 600, color: token.colorTextSecondary }}>
            Actions correctives suggérées
          </h3>
          <Space direction="vertical" style={{ width: '100%' }}>
            <Skeleton.Button active size="default" block />
            <Skeleton.Button active size="default" block />
          </Space>
        </section>
      )}

      {hasSuggestions && !suggestionsLoading && (
        <section
          aria-labelledby="structured-error-remediation-heading"
          style={{ marginBottom: 16 }}
          data-testid="remediation-suggestions-section"
        >
          <h3
            id="structured-error-remediation-heading"
            style={{ margin: '0 0 8px 0', fontSize: 14, fontWeight: 600, color: token.colorTextSecondary }}
          >
            Actions correctives suggérées
          </h3>
          <Space direction="vertical" style={{ width: '100%' }}>
            {remediationSuggestions!.map((suggestion, index) => (
              <Tooltip
                key={suggestion.action_id}
                title={suggestion.action_description || 'Aucune description'}
              >
                <Button
                  type={index === 0 ? 'primary' : 'default'}
                  danger={index === 0}
                  icon={<ToolOutlined />}
                  onClick={() => onSuggestionClick?.(suggestion)}
                  style={{ width: '100%', textAlign: 'left' }}
                  aria-label={`Exécuter action corrective: ${suggestion.action_name}`}
                  data-testid={`remediation-suggestion-${suggestion.action_id}`}
                >
                  {suggestion.action_name}
                </Button>
              </Tooltip>
            ))}
          </Space>
        </section>
      )}

      <section>
        <h3 style={{ margin: '0 0 8px 0', fontSize: 14, fontWeight: 600, color: token.colorTextSecondary }}>
          Options
        </h3>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
          {/* Story 7.2, Task 3.4/3.5: Reorder buttons for business variant - Contact DBA is primary */}
          {variant === 'business' ? (
            <>
              <Button
                ref={firstOptionRef}
                type="primary"
                onClick={onContact}
                disabled={!onContact}
                style={{ outlineOffset: 2 }}
              >
                Contacter DBA
              </Button>
              <Button onClick={onRetry} disabled={!onRetry} style={{ outlineOffset: 2 }}>
                Relancer
              </Button>
              <Button type="text" onClick={onViewLogs} disabled={!onViewLogs} style={{ outlineOffset: 2 }}>
                Voir logs
              </Button>
            </>
          ) : (
            <>
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
            </>
          )}
        </div>
      </section>
    </div>
  );
}

/**
 * Execution status renderer — Rendu de statut d'exécution pour les colonnes de tableau.
 *
 * Config LOCALE — NE PAS fusionner avec execution-status.ts (SOLID-FE-10, §16.4).
 * Voir commentaires de STATUS_BADGE_CONFIG et STATUS_CONFIG pour les différences intentionnelles.
 *
 * Extrait de executionRenderers.tsx (Story 54.13 — MAINT-FE-3).
 */

/* eslint-disable react-refresh/only-export-components */

import { Badge, Tag, theme } from 'antd';
import {
  CheckCircleOutlined,
  CloseCircleOutlined,
  ClockCircleOutlined,
  SyncOutlined,
  PauseCircleOutlined,
  StopOutlined,
  MinusCircleOutlined,
  ExclamationCircleOutlined,
} from '@ant-design/icons';
import type { ExecutionStatusType } from '../types/api';
import { STYLE_TOKENS } from '../theme/styleTokens';

/**
 * Status badge configuration for StatusIndicator component (AC2, AC3).
 * - processing: Pulsing animation for running states
 * - success/error/default/warning: Fixed color for terminal states
 *
 * SOLID-FE-10 — config locale justifiée : NE PAS remplacer par EXECUTION_STATUS_BADGE_CONFIG.
 * Différences intentionnelles avec execution-status.ts :
 *   1. Labels FÉMININS ("Soumise", "Terminée", "Annulée") pour renderers de colonnes inline
 *      (vs. masculins "Soumis", "Terminé", "Annulé" dans EXECUTION_STATUS_BADGE_CONFIG pour ExecutionView standalone)
 *   2. Champ `color` (hex) pour la bordure du Tag — absent de EXECUTION_STATUS_BADGE_CONFIG (BadgeStatusType uniquement)
 *   3. PENDING_APPROVAL = "En attente" (court) vs "En attente approbation" (précis) — usage différent
 * Privé : consommé uniquement par StatusIndicator dans ce fichier.
 */
const STATUS_BADGE_CONFIG: Record<
  ExecutionStatusType,
  {
    status: 'processing' | 'success' | 'error' | 'default' | 'warning';
    label: string;
    color: string;
  }
> = {
  SUBMITTED: { status: 'processing', label: 'Soumise', color: '#3B82F6' },
  INTEGRATION_ERROR: { status: 'error', label: 'Erreur intégration', color: '#EF4444' },
  PENDING_APPROVAL: { status: 'processing', label: 'En attente', color: '#F59E0B' },
  RUNNING: { status: 'processing', label: 'En cours', color: '#3B82F6' },
  COMPLETED: { status: 'success', label: 'Terminée', color: '#10B981' },
  FAILED: { status: 'error', label: 'Échouée', color: '#EF4444' },
  CANCELLED: { status: 'default', label: 'Annulée', color: '#9CA3AF' },
  REJECTED: { status: 'warning', label: 'Rejetée', color: '#F59E0B' },
};

/**
 * StatusIndicator component for Statut column (AC1, AC2, AC3).
 *
 * Uses theme tokens for background/border/text colors (Story 30.11 AC2).
 * - Running states (SUBMITTED, PENDING_APPROVAL, RUNNING): Tag with pulsing dot indicator
 * - Terminal states (COMPLETED, FAILED, CANCELLED, REJECTED): Tag with colored dot
 */
function StatusIndicator({ status }: { status: ExecutionStatusType }): React.ReactNode {
  const { token } = theme.useToken();
  const config = STATUS_BADGE_CONFIG[status] || {
    status: 'default' as const,
    label: 'Inconnu',
    color: '#9CA3AF',
  };
  const isRunning = config.status === 'processing';

  const borderColor = config.color;
  const textColor =
    config.status === 'error'
      ? STYLE_TOKENS.textError
      : config.status === 'success'
        ? STYLE_TOKENS.textSuccess
        : config.status === 'warning'
          ? STYLE_TOKENS.textWarning
          : config.status === 'processing'
            ? config.color
            : token.colorText;

  return (
    <Tag
      style={{
        margin: 0,
        display: 'inline-flex',
        alignItems: 'center',
        gap: 8,
        border: `1px solid ${borderColor}`,
        backgroundColor: token.colorBgElevated,
        color: textColor,
        padding: '1px 6px',
        fontSize: '12px',
        lineHeight: '20px',
        backdropFilter: 'blur(8px)',
      }}
    >
      <Badge
        status={config.status}
        style={{
          transform: isRunning ? 'scale(2.0)' : 'scale(1.3)',
          display: 'inline-block',
        }}
      />
      <span style={{ fontWeight: 500 }}>{config.label}</span>
    </Tag>
  );
}

/**
 * Render status indicator badge for Statut column (AC1, AC2, AC3).
 * Wrapper function for backward compatibility with column render functions.
 *
 * @param status - Execution status
 * @returns React node with Tag containing badge dot + text label
 */
export function renderStatusIndicator(status: ExecutionStatusType): React.ReactNode {
  return <StatusIndicator status={status} />;
}

// Status config avec icons — config locale justifiée (SOLID-FE-10).
// Usage Icon (RecentExecutions) + couleur hex ≠ Badge Ant Design (BadgeStatusType).
// EXECUTION_STATUS_BADGE_CONFIG (utils/execution-status.ts) = badges sans icônes.
// Ce config inclut Icon component (ClockCircleOutlined, SyncOutlined…) absent de la source partagée.
// Consommateurs : RecentExecutions.tsx — ne pas supprimer ni migrer vers execution-status.ts.
export const STATUS_CONFIG: Record<
  ExecutionStatusType,
  { label: string; Icon: React.ComponentType<{ spin?: boolean; style?: React.CSSProperties }>; color: string }
> = {
  SUBMITTED: { label: 'Soumise', Icon: ClockCircleOutlined, color: '#3B82F6' },
  INTEGRATION_ERROR: { label: 'Erreur intégration', Icon: ExclamationCircleOutlined, color: '#EF4444' },
  PENDING_APPROVAL: { label: 'En attente', Icon: PauseCircleOutlined, color: '#F59E0B' },
  RUNNING: { label: 'En cours', Icon: SyncOutlined, color: '#3B82F6' },
  COMPLETED: { label: 'Terminée', Icon: CheckCircleOutlined, color: '#10B981' },
  FAILED: { label: 'Échouée', Icon: CloseCircleOutlined, color: '#EF4444' },
  CANCELLED: { label: 'Annulée', Icon: StopOutlined, color: '#9CA3AF' },
  REJECTED: { label: 'Rejetée', Icon: MinusCircleOutlined, color: '#F59E0B' },
};

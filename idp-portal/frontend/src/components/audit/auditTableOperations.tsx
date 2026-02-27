/**
 * Operation config helpers for AuditTable.
 * Extracted to satisfy react-refresh/only-export-components.
 */

import type { ReactNode } from 'react';
import {
  PlusOutlined,
  EditOutlined,
  DeleteOutlined,
  CheckCircleOutlined,
  CloseOutlined,
  PlayCircleOutlined,
  ExclamationCircleOutlined,
  StopOutlined,
  SyncOutlined,
  ClockCircleOutlined,
  SendOutlined,
} from '@ant-design/icons';

export interface OperationConfig {
  label: string;
  icon: ReactNode;
  color: string;
}

const OPERATION_SUFFIX_MAP: Array<{ suffix: string; config: OperationConfig }> = [
  { suffix: '_PENDING_APPROVAL', config: { label: 'En attente', icon: <ClockCircleOutlined />, color: 'orange' } },
  { suffix: '_APPROVED', config: { label: 'Approuver', icon: <CheckCircleOutlined />, color: 'green' } },
  { suffix: '_REJECTED', config: { label: 'Rejeter', icon: <CloseOutlined />, color: 'red' } },
  { suffix: '_PUBLISHED', config: { label: 'Publier', icon: <CheckCircleOutlined />, color: 'green' } },
  { suffix: '_SUBMITTED', config: { label: 'Soumettre', icon: <SendOutlined />, color: 'blue' } },
  { suffix: '_COMPLETED', config: { label: 'Terminer', icon: <CheckCircleOutlined />, color: 'green' } },
  { suffix: '_FAILED', config: { label: 'Échouer', icon: <ExclamationCircleOutlined />, color: 'red' } },
  { suffix: '_CANCELLED', config: { label: 'Annuler', icon: <StopOutlined />, color: 'volcano' } },
  { suffix: '_RUNNING', config: { label: 'Démarrer', icon: <PlayCircleOutlined />, color: 'blue' } },
  { suffix: '_DELETED', config: { label: 'Supprimer', icon: <DeleteOutlined />, color: 'red' } },
  { suffix: '_CREATED', config: { label: 'Créer', icon: <PlusOutlined />, color: 'green' } },
  { suffix: '_UPDATED', config: { label: 'Modifier', icon: <EditOutlined />, color: 'blue' } },
  { suffix: '_DISABLED', config: { label: 'Désactiver', icon: <StopOutlined />, color: 'orange' } },
  { suffix: '_ENABLED', config: { label: 'Activer', icon: <CheckCircleOutlined />, color: 'green' } },
  { suffix: '_REACTIVATED', config: { label: 'Réactiver', icon: <SyncOutlined />, color: 'blue' } },
  { suffix: '_DEACTIVATED', config: { label: 'Désactiver', icon: <StopOutlined />, color: 'orange' } },
  { suffix: '_EXECUTED', config: { label: 'Exécuter', icon: <PlayCircleOutlined />, color: 'blue' } },
  { suffix: '_TRIGGERED', config: { label: 'Déclencher', icon: <PlayCircleOutlined />, color: 'blue' } },
  { suffix: '_BLOCKED', config: { label: 'Bloquer', icon: <CloseOutlined />, color: 'red' } },
  { suffix: '_FORBIDDEN', config: { label: 'Interdit', icon: <CloseOutlined />, color: 'red' } },
  { suffix: '_BLOCKED_INVALID_INTEGRATION', config: { label: 'Bloquer', icon: <CloseOutlined />, color: 'red' } },
  { suffix: '_INVALID_INTEGRATION', config: { label: 'Bloquer', icon: <CloseOutlined />, color: 'red' } },
  { suffix: '_INTEGRATION', config: { label: 'Intégration', icon: <ExclamationCircleOutlined />, color: 'orange' } },
  { suffix: '_EXHAUSTED', config: { label: 'Polling épuisé', icon: <ExclamationCircleOutlined />, color: 'orange' } },
  { suffix: '_WARNING', config: { label: 'Avertissement', icon: <ExclamationCircleOutlined />, color: 'orange' } },
];

const FALLBACK_OPERATION: OperationConfig = { label: '—', icon: null, color: 'default' };

export function getOperationConfig(actionType: string): OperationConfig {
  if (!actionType) return FALLBACK_OPERATION;
  for (const { suffix, config } of OPERATION_SUFFIX_MAP) {
    if (actionType.endsWith(suffix)) return config;
  }
  return FALLBACK_OPERATION;
}

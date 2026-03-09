/**
 * KeyValueEditor — Composant réutilisable pour éditer des paires clé-valeur (Story 57.13).
 * Utilisé pour input_mapping, output_mapping, headers, params.
 *
 * Note: utilise un état interne pour permettre l'édition de clés vides
 * (les lignes restent visibles pendant la saisie ; seules les clés non-vides
 * sont émises vers le parent via onChange).
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import type { FC, ReactNode } from 'react';
import { Alert, Button, Input, Space, theme } from 'antd';
import type { InputRef } from 'antd';
import { DeleteOutlined, PlusOutlined } from '@ant-design/icons';
import { VariablePicker } from '../workflow/VariablePicker';

export interface KeyValueEditorProps {
  value?: Record<string, string> | null;
  onChange: (value: Record<string, string>) => void;
  disabled?: boolean;
  keyPlaceholder?: string;
  valuePlaceholder?: string;
  'data-testid'?: string;
  /** Story 57.20: Contenu d'aide affiché à côté du label (ex. MappingHelpPopover). */
  helpContent?: ReactNode;
  /** Story 57.20: Label affiché au-dessus de l'éditeur. */
  label?: string;
  /** Story 57.20: Avertissements à afficher sous l'éditeur. */
  warnings?: string[];
  /** Story 57.20: Step options with readable labels for MappingHelpPopover. */
  availableStepOptions?: { value: string; label: string }[];
  /** Story 63.3: workflow ID for output schema context (VariablePicker). */
  workflowId?: number;
  /** Story 63.3: current step ID for VariablePicker. */
  currentStepId?: string | null;
  /** Story 63.3: available step IDs for VariablePicker. */
  availableStepIds?: string[];
}

interface KvPair {
  key: string;
  value: string;
}

function recordToPairs(record?: Record<string, string> | null): KvPair[] {
  if (!record) return [];
  return Object.entries(record).map(([key, value]) => ({ key, value }));
}

function pairsToRecord(pairs: KvPair[]): Record<string, string> {
  return pairs.reduce<Record<string, string>>((acc, { key, value }) => {
    if (key) acc[key] = value;
    return acc;
  }, {});
}

export const KeyValueEditor: FC<KeyValueEditorProps> = ({
  value,
  onChange,
  disabled = false,
  keyPlaceholder = 'Clé',
  valuePlaceholder = 'Valeur',
  'data-testid': testId,
  helpContent,
  label,
  warnings,
  workflowId,
  currentStepId,
  availableStepIds,
}) => {
  const { token } = theme.useToken();
  // Internal state keeps empty-key rows visible during typing
  const [localPairs, setLocalPairs] = useState<KvPair[]>(() => recordToPairs(value));
  const valueInputRefs = useRef<(InputRef | null)[]>([]);
  // Track cursor position on blur so VariablePicker inserts at the right position
  const lastCursorPositions = useRef<Array<{ start: number; end: number } | null>>([]);
  const showVariablePicker = workflowId !== undefined && Boolean(currentStepId);

  // Track last emitted value to detect external changes without triggering on our own updates
  const lastEmitted = useRef<Record<string, string> | null | undefined>(value);

  // Sync external value changes (e.g. parent resets the field) into local state
  useEffect(() => {
    if (value !== lastEmitted.current) {
      lastEmitted.current = value;
      setLocalPairs(recordToPairs(value));
    }
  }, [value]);

  const emitChange = useCallback(
    (pairs: KvPair[]) => {
      const record = pairsToRecord(pairs);
      lastEmitted.current = record;
      onChange(record);
    },
    [onChange],
  );

  const handleKeyChange = useCallback(
    (index: number, newKey: string) => {
      const updated = localPairs.map((p, i) => (i === index ? { ...p, key: newKey } : p));
      setLocalPairs(updated);
      emitChange(updated);
    },
    [localPairs, emitChange],
  );

  const handleValueChange = useCallback(
    (index: number, newValue: string) => {
      const updated = localPairs.map((p, i) => (i === index ? { ...p, value: newValue } : p));
      setLocalPairs(updated);
      emitChange(updated);
    },
    [localPairs, emitChange],
  );

  const handleAdd = useCallback(() => {
    const updated = [...localPairs, { key: '', value: '' }];
    setLocalPairs(updated);
    // Do not emit — empty key is intentionally excluded from parent state until user types it
  }, [localPairs]);

  const handleRemove = useCallback(
    (index: number) => {
      const updated = localPairs.filter((_, i) => i !== index);
      setLocalPairs(updated);
      emitChange(updated);
    },
    [localPairs, emitChange],
  );

  const handleVariableInsert = useCallback(
    (rowIndex: number, expression: string) => {
      const input = valueInputRefs.current[rowIndex];
      if (input?.input) {
        const el = input.input;
        const saved = lastCursorPositions.current[rowIndex];
        const current = localPairs[rowIndex]?.value ?? '';
        const start = saved?.start ?? current.length;
        const end = saved?.end ?? current.length;
        const newValue = current.slice(0, start) + expression + current.slice(end);
        handleValueChange(rowIndex, newValue);
        requestAnimationFrame(() => {
          el.focus();
          const cursor = start + expression.length;
          el.setSelectionRange(cursor, cursor);
        });
      } else {
        const current = localPairs[rowIndex]?.value ?? '';
        handleValueChange(rowIndex, current + expression);
      }
    },
    [localPairs, handleValueChange],
  );

  return (
    <div data-testid={testId}>
      {label && (
        <Space style={{ marginBottom: 4 }} size={4}>
          <span style={{ fontSize: 12, color: token.colorTextSecondary }}>{label}</span>
          {helpContent}
        </Space>
      )}
      {!label && helpContent && (
        <div style={{ marginBottom: 4 }}>{helpContent}</div>
      )}
      {localPairs.map((pair, index) => (
        <Space key={index} style={{ display: 'flex', marginBottom: 4 }} align="center">
          <Input
            size="small"
            value={pair.key}
            onChange={(e) => handleKeyChange(index, e.target.value)}
            placeholder={keyPlaceholder}
            disabled={disabled}
            style={{ width: 140 }}
            aria-label={`${keyPlaceholder} ${index + 1}`}
          />
          <Input
            size="small"
            ref={(el) => { valueInputRefs.current[index] = el; }}
            value={pair.value}
            onChange={(e) => handleValueChange(index, e.target.value)}
            onBlur={(e) => {
              lastCursorPositions.current[index] = {
                start: e.target.selectionStart ?? (localPairs[index]?.value ?? '').length,
                end: e.target.selectionEnd ?? (localPairs[index]?.value ?? '').length,
              };
            }}
            placeholder={valuePlaceholder}
            disabled={disabled}
            style={{ width: 160 }}
            aria-label={`${valuePlaceholder} ${index + 1}`}
          />
          {showVariablePicker && (
            <VariablePicker
              workflowId={workflowId}
              currentStepId={currentStepId ?? ''}
              availableStepIds={availableStepIds}
              onSelect={(expr) => handleVariableInsert(index, expr)}
              disabled={disabled}
            />
          )}
          {!disabled && (
            <Button
              size="small"
              type="text"
              danger
              icon={<DeleteOutlined />}
              onClick={() => handleRemove(index)}
              aria-label={`Supprimer l'entrée ${index + 1}`}
            />
          )}
        </Space>
      ))}
      {!disabled && (
        <Button
          size="small"
          type="dashed"
          icon={<PlusOutlined />}
          onClick={handleAdd}
          style={{ marginTop: 4 }}
        >
          Ajouter une entrée
        </Button>
      )}
      {warnings && warnings.length > 0 && (
        <Alert
          type="warning"
          showIcon
          title={warnings.join(' ; ')}
          style={{ marginTop: 4 }}
          data-testid={testId ? `${testId}-warning` : 'kv-warning'}
        />
      )}
    </div>
  );
};

export default KeyValueEditor;

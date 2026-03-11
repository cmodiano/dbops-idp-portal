/**
 * FormattedJson — Story 72.4
 *
 * Composant réutilisable pour afficher des valeurs JSON avec indentation.
 * Centralise le pattern JSON.stringify(value, null, 2) répété dans le codebase.
 */

import type { CSSProperties } from 'react';

export interface FormattedJsonProps {
  value: unknown;
  maxHeight?: number;
  style?: CSSProperties;
}

/** Try to format value as JSON; returns null if circular or non-serializable. */
function safeStringify(value: unknown): string | null {
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return null;
  }
}

/** If value is a string that parses to JSON object/array, return parsed; else return null. */
function tryParseJsonString(s: string): unknown | null {
  try {
    const parsed = JSON.parse(s);
    return typeof parsed === 'object' && parsed !== null ? parsed : null;
  } catch {
    return null;
  }
}

/**
 * Affiche une valeur JSON avec indentation 2 espaces dans un bloc <pre>.
 * - null/undefined → '—'
 * - object/array → JSON.stringify(value, null, 2) dans <pre>
 * - string contenant JSON → parsé et formaté si possible
 * - string/number/boolean → String(value)
 * - références circulaires → message de fallback
 */
export function FormattedJson({ value, maxHeight, style }: FormattedJsonProps) {
  if (value === null || value === undefined) {
    return <span>—</span>;
  }

  // M4: string that looks like JSON — try parse and format
  if (typeof value === 'string' && (value.trim().startsWith('{') || value.trim().startsWith('['))) {
    const parsed = tryParseJsonString(value);
    if (parsed !== null) {
      const formatted = safeStringify(parsed);
      if (formatted !== null) {
        const preStyle: CSSProperties = {
          margin: 0,
          fontSize: 11,
          whiteSpace: 'pre-wrap',
          wordBreak: 'break-word',
          ...(maxHeight !== undefined ? { maxHeight, overflow: 'auto' } : {}),
          ...style,
        };
        return <pre style={preStyle} aria-label="JSON formaté">{formatted}</pre>;
      }
    }
  }

  if (typeof value === 'object') {
    const formatted = safeStringify(value);
    if (formatted === null) {
      return <span style={style}>[Référence circulaire ou non sérialisable]</span>;
    }
    const preStyle: CSSProperties = {
      margin: 0,
      fontSize: 11,
      whiteSpace: 'pre-wrap',
      wordBreak: 'break-word',
      ...(maxHeight !== undefined ? { maxHeight, overflow: 'auto' } : {}),
      ...style,
    };
    return <pre style={preStyle} aria-label="JSON formaté">{formatted}</pre>;
  }

  return <span style={style}>{String(value)}</span>;
}

/**
 * FormattedJson — Story 72.4
 *
 * Composant réutilisable pour afficher des valeurs JSON.
 * - asTable: true → rendu en tableau (Story 72.4, lisibilité pour auditeurs)
 * - sinon → indentation JSON classique
 */

import type { CSSProperties } from 'react';
import { Table } from 'antd';
import type { TableProps } from 'antd';

export interface FormattedJsonProps {
  value: unknown;
  maxHeight?: number;
  style?: CSSProperties;
  /** Story 72.4: afficher objets/tableaux en format tableau lisible */
  asTable?: boolean;
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

/** Story 72.4: rendu tableau pour objets — colonnes Clé, Valeur */
function renderObjectAsTable(obj: Record<string, unknown>, style?: CSSProperties) {
  const dataSource = Object.entries(obj).map(([key, val], i) => {
    let valeur: string;
    if (val === null || val === undefined) {
      valeur = '—';
    } else if (typeof val === 'object') {
      valeur = safeStringify(val) ?? '—';
    } else {
      valeur = String(val);
    }
    return { key: `${key}-${i}`, cle: key, valeur: valeur || '—' };
  });
  const columns: TableProps<{ key: string; cle: string; valeur: string }>['columns'] = [
    { title: 'Clé', dataIndex: 'cle', key: 'cle', width: 140 },
    { title: 'Valeur', dataIndex: 'valeur', key: 'valeur', minWidth: 120, ellipsis: false },
  ];
  return (
    <Table
      dataSource={dataSource}
      columns={columns}
      pagination={false}
      size="small"
      style={{ ...style, fontSize: 11 }}
    />
  );
}

/** Story 72.4: rendu tableau pour tableaux — une colonne Valeur */
function renderArrayAsTable(arr: unknown[], style?: CSSProperties) {
  const isArrayOfObjects =
    arr.length > 0 &&
    arr.every((item) => typeof item === 'object' && item !== null && !Array.isArray(item));
  if (isArrayOfObjects) {
    const first = arr[0] as Record<string, unknown>;
    const keys = Object.keys(first);
    const dataSource = arr.map((item, i) => ({
      key: String(i),
      ...(typeof item === 'object' && item !== null ? (item as Record<string, unknown>) : {}),
    }));
    const columns: TableProps<Record<string, unknown>>['columns'] = keys.map((k) => ({
      title: k,
      dataIndex: k,
      key: k,
      render: (v: unknown) =>
        typeof v === 'object' && v !== null ? safeStringify(v) ?? String(v) : String(v ?? '—'),
    }));
    return (
      <Table
        dataSource={dataSource}
        columns={columns}
        pagination={false}
        size="small"
        style={{ ...style, fontSize: 11 }}
      />
    );
  }
  const dataSource = arr.map((item, i) => ({
    key: String(i),
    valeur: typeof item === 'object' && item !== null ? safeStringify(item) ?? String(item) : String(item ?? '—'),
  }));
  const columns: TableProps<{ key: string; valeur: string }>['columns'] = [
    { title: 'Valeur', dataIndex: 'valeur', key: 'valeur' },
  ];
  return (
    <Table
      dataSource={dataSource}
      columns={columns}
      pagination={false}
      size="small"
      style={{ ...style, fontSize: 11 }}
    />
  );
}

/**
 * Affiche une valeur JSON.
 * - asTable: true et object/array → rendu en tableau (Story 72.4)
 * - sinon → indentation JSON classique dans <pre>
 */
export function FormattedJson({ value, maxHeight, style, asTable = false }: FormattedJsonProps) {
  if (value === null || value === undefined) {
    return <span>—</span>;
  }

  // Story 72.4: rendu tableau pour objets et tableaux
  if (asTable && typeof value === 'object') {
    if (Array.isArray(value)) {
      return renderArrayAsTable(value, style);
    }
    return renderObjectAsTable(value as Record<string, unknown>, style);
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

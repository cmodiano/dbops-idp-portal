/**
 * Tests for FormattedJson — Story 72.4
 */

import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { FormattedJson } from './FormattedJson';

describe('FormattedJson', () => {
  it('affiche "—" pour null', () => {
    render(<FormattedJson value={null} />);
    expect(screen.getByText('—')).toBeInTheDocument();
  });

  it('affiche "—" pour undefined', () => {
    render(<FormattedJson value={undefined} />);
    expect(screen.getByText('—')).toBeInTheDocument();
  });

  it('affiche une string telle quelle', () => {
    render(<FormattedJson value="hello world" />);
    expect(screen.getByText('hello world')).toBeInTheDocument();
  });

  it('affiche un nombre tel quel', () => {
    render(<FormattedJson value={42} />);
    expect(screen.getByText('42')).toBeInTheDocument();
  });

  it('affiche un booléen tel quel', () => {
    render(<FormattedJson value={true} />);
    expect(screen.getByText('true')).toBeInTheDocument();
  });

  it('affiche un objet JSON indenté dans un <pre>', () => {
    const obj = { key: 'value', nested: { a: 1 } };
    const { container } = render(<FormattedJson value={obj} />);
    const pre = container.querySelector('pre');
    expect(pre).toBeInTheDocument();
    expect(pre?.textContent).toBe(JSON.stringify(obj, null, 2));
  });

  it('affiche un tableau JSON indenté dans un <pre>', () => {
    const arr = [1, 'deux', { three: 3 }];
    const { container } = render(<FormattedJson value={arr} />);
    const pre = container.querySelector('pre');
    expect(pre).toBeInTheDocument();
    expect(pre?.textContent).toBe(JSON.stringify(arr, null, 2));
  });

  it('applique maxHeight et overflow auto sur le <pre>', () => {
    const { container } = render(<FormattedJson value={{ a: 1 }} maxHeight={200} />);
    const pre = container.querySelector('pre');
    expect(pre).toHaveStyle({ maxHeight: '200px', overflow: 'auto' });
  });

  it('applique le style personnalisé', () => {
    const { container } = render(
      <FormattedJson value={{ a: 1 }} style={{ fontSize: 14 }} />,
    );
    const pre = container.querySelector('pre');
    expect(pre).toHaveStyle({ fontSize: '14px' });
  });

  it('gère un objet imbriqué complexe', () => {
    const nested = { level1: { level2: { level3: 'deep' } }, arr: [1, 2, 3] };
    const { container } = render(<FormattedJson value={nested} />);
    const pre = container.querySelector('pre');
    expect(pre?.textContent).toBe(JSON.stringify(nested, null, 2));
  });

  it('parse et formate une string contenant du JSON (M4)', () => {
    const jsonStr = '{"key":"value","nested":{"a":1}}';
    const { container } = render(<FormattedJson value={jsonStr} />);
    const pre = container.querySelector('pre');
    expect(pre).toBeInTheDocument();
    expect(pre?.textContent).toBe(JSON.stringify(JSON.parse(jsonStr), null, 2));
  });

  it('affiche un fallback pour références circulaires (M2)', () => {
    const circular: Record<string, unknown> = { a: 1 };
    circular.self = circular;
    render(<FormattedJson value={circular} />);
    expect(screen.getByText(/Référence circulaire ou non sérialisable/)).toBeInTheDocument();
  });
});

/**
 * Story 18.2 — Task 6: Tests for getItemTypeIcon shared utility.
 */
import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/react';
import { getItemTypeIcon, WORKFLOW_COLOR } from './iconHelpers';

describe('getItemTypeIcon', () => {
  it('returns ApartmentOutlined violet for workflow', () => {
    const result = getItemTypeIcon('workflow', null);
    expect(result.color).toBe(WORKFLOW_COLOR);
    expect(result.label).toBe("Workflow (chaîne d'actions)");

    const { container } = render(<>{result.icon}</>);
    const icon = container.querySelector('.anticon-apartment');
    expect(icon).toBeInTheDocument();
    expect(container.querySelector('[aria-label="Type: Workflow"]')).toBeInTheDocument();
  });

  it('returns DatabaseOutlined for action oracle', () => {
    const result = getItemTypeIcon('action', 'Oracle');
    expect(result.label).toBe('Action Oracle');

    const { container } = render(<>{result.icon}</>);
    expect(container.querySelector('.anticon-database')).toBeInTheDocument();
    expect(container.querySelector('[aria-label="Type: Action Oracle"]')).toBeInTheDocument();
  });

  it('returns CloudServerOutlined for action sqlserver', () => {
    const result = getItemTypeIcon('action', 'SQL Server');
    expect(result.label).toBe('Action SQL Server');

    const { container } = render(<>{result.icon}</>);
    expect(container.querySelector('.anticon-cloud-server')).toBeInTheDocument();
    expect(container.querySelector('[aria-label="Type: Action SQL Server"]')).toBeInTheDocument();
  });

  it('returns HddOutlined for action db2', () => {
    const result = getItemTypeIcon('action', 'DB2');
    expect(result.label).toBe('Action DB2');

    const { container } = render(<>{result.icon}</>);
    expect(container.querySelector('.anticon-hdd')).toBeInTheDocument();
    expect(container.querySelector('[aria-label="Type: Action DB2"]')).toBeInTheDocument();
  });

  it('returns HddOutlined grey for unknown engine (fallback)', () => {
    const result = getItemTypeIcon('action', 'PostgreSQL');
    expect(result.color).toBe('#8c8c8c');
    expect(result.label).toBe('Action PostgreSQL');

    const { container } = render(<>{result.icon}</>);
    expect(container.querySelector('.anticon-hdd')).toBeInTheDocument();
    expect(container.querySelector('[aria-label="Type: Action PostgreSQL"]')).toBeInTheDocument();
  });

  it('returns HddOutlined grey for null engine', () => {
    const result = getItemTypeIcon('action', null);
    expect(result.color).toBe('#8c8c8c');
    expect(result.label).toBe('Action inconnu');
  });

  it('wraps in Tooltip when withTooltip is true', () => {
    const result = getItemTypeIcon('workflow', null, { withTooltip: true });
    const { container } = render(<>{result.icon}</>);
    // Tooltip wraps the icon — the icon should still be present
    expect(container.querySelector('.anticon-apartment')).toBeInTheDocument();
  });

  it('respects custom fontSize option', () => {
    const result = getItemTypeIcon('workflow', null, { fontSize: 24 });
    const { container } = render(<>{result.icon}</>);
    const icon = container.querySelector('.anticon-apartment');
    expect(icon).toBeInTheDocument();
  });
});

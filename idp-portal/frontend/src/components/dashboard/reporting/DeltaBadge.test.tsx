/**
 * Tests for DeltaBadge component (Story 8.6, AC5).
 */

import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { DeltaBadge } from './DeltaBadge';

describe('DeltaBadge', () => {
  it('renders positive delta with green color and up arrow', () => {
    render(<DeltaBadge delta={25.5} />);

    expect(screen.getByText('+25.5%')).toBeInTheDocument();
    // Check for up arrow icon
    expect(document.querySelector('.anticon-arrow-up')).toBeInTheDocument();
  });

  it('renders negative delta with red color and down arrow', () => {
    render(<DeltaBadge delta={-15.2} />);

    expect(screen.getByText('-15.2%')).toBeInTheDocument();
    // Check for down arrow icon
    expect(document.querySelector('.anticon-arrow-down')).toBeInTheDocument();
  });

  it('renders zero delta with neutral styling', () => {
    render(<DeltaBadge delta={0} />);

    expect(screen.getByText('0%')).toBeInTheDocument();
    // Check for minus icon (neutral)
    expect(document.querySelector('.anticon-minus')).toBeInTheDocument();
  });

  it('renders null delta as 0%', () => {
    render(<DeltaBadge delta={null} />);

    expect(screen.getByText('0%')).toBeInTheDocument();
  });

  it('inverts colors when invertColors prop is true (for metrics where lower is better)', () => {
    // Positive delta with inverted colors should be red (bad)
    const { container } = render(<DeltaBadge delta={10} invertColors />);

    // Check the tag has red styling when inverted
    const tag = container.querySelector('.ant-tag-red');
    expect(tag).toBeInTheDocument();
  });

  it('renders very small delta values correctly', () => {
    render(<DeltaBadge delta={0.05} />);

    expect(screen.getByText('+0.1%')).toBeInTheDocument();
  });

  it('renders large delta values correctly', () => {
    render(<DeltaBadge delta={150.75} />);

    expect(screen.getByText('+150.8%')).toBeInTheDocument();
  });
});

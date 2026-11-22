import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { SeverityBadge } from '../components/common/SeverityBadge';
import { StatusBadge } from '../components/common/StatusBadge';
import { ConfidenceBadge } from '../components/common/ConfidenceBadge';

describe('Common Badges', () => {
  it('renders Critical SeverityBadge correctly', () => {
    render(<SeverityBadge severity="CRITICAL" />);
    expect(screen.getByText('CRITICAL')).toBeInTheDocument();
  });

  it('renders High and Medium SeverityBadges', () => {
    const { rerender } = render(<SeverityBadge severity="HIGH" />);
    expect(screen.getByText('HIGH')).toBeInTheDocument();

    rerender(<SeverityBadge severity="MEDIUM" />);
    expect(screen.getByText('MEDIUM')).toBeInTheDocument();
  });

  it('renders StatusBadge with OPEN, ACKNOWLEDGED, RESOLVED', () => {
    const { rerender } = render(<StatusBadge status="OPEN" />);
    expect(screen.getByText('OPEN')).toBeInTheDocument();

    rerender(<StatusBadge status="ACKNOWLEDGED" />);
    expect(screen.getByText('ACKNOWLEDGED')).toBeInTheDocument();

    rerender(<StatusBadge status="RESOLVED" />);
    expect(screen.getByText('RESOLVED')).toBeInTheDocument();
  });

  it('renders ConfidenceBadge with high confidence', () => {
    render(<ConfidenceBadge confidence="HIGH" />);
    expect(screen.getByText('HIGH CONFIDENCE')).toBeInTheDocument();
  });
});

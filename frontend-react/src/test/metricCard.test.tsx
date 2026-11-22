import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MetricCard } from '../components/common/MetricCard';

describe('MetricCard', () => {
  it('renders title, value, and subtitle', () => {
    render(
      <MetricCard
        title="Open Incidents"
        value={12}
        subtitle="Requiring immediate triage"
      />
    );
    expect(screen.getByText('Open Incidents')).toBeInTheDocument();
    expect(screen.getByText('12')).toBeInTheDocument();
    expect(screen.getByText('Requiring immediate triage')).toBeInTheDocument();
  });

  it('renders positive trend indicator', () => {
    render(
      <MetricCard
        title="Resolution Rate"
        value="95%"
        trend="+5%"
        trendPositive={true}
      />
    );
    expect(screen.getByText('95%')).toBeInTheDocument();
    expect(screen.getByText('+5%')).toHaveClass('text-emerald-400');
  });
});

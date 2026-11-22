import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { aggregateAdvertisers } from '../aggregate';
import { DEFAULT_ADVERTISER_FILTERS, kpis } from '../filters';
import { buildGraph } from '../graph';
import type { AdvertiserFinding } from '../model';
import { AdvertisersOverview } from './AdvertisersOverview';

let n = 0;
const f = (handle: string, firm: string | null): AdvertiserFinding => ({
  id: `o-${++n}`,
  module: 'M1',
  advertiser: { handle },
  firm: firm ? { name: firm, registryId: `r-${firm}` } : null,
});
const rows = aggregateAdvertisers([f('@a', 'X'), f('@a', 'Y'), f('@b', 'X'), f('@c', null)]);

function props(patch: Partial<Parameters<typeof AdvertisersOverview>[0]> = {}) {
  return {
    rows,
    graph: buildGraph(rows),
    kpis: kpis(rows),
    loaded: 11,
    total: 11,
    isLoading: false,
    isError: false,
    filters: DEFAULT_ADVERTISER_FILTERS,
    onFiltersChange: vi.fn(),
    view: 'graph' as const,
    onViewChange: vi.fn(),
    selected: 'h:@a',
    onSelect: vi.fn(),
    relationHref: () => '#',
    onOpenRelation: vi.fn(),
    ...patch,
  };
}

describe('AdvertisersOverview', () => {
  it('states the KPI sentence with the repeat count in its own element', () => {
    const { container } = render(<AdvertisersOverview {...props()} />);
    expect(screen.getByRole('heading', { name: 'POWIĄZANIA · M1 · FINFLUENCERZY I FIRMY Z REJESTRU' })).toBeInTheDocument();
    expect(container.querySelector('.adv-figures')).toHaveTextContent('3 reklamodawców promuje 2 licencjonowane firmy, w tym 1 powtarzający się');
    expect(container.querySelector('[data-kpi="repeat"]')).toHaveClass('hero-value-risk');
  });

  it('uses Polish plurals in the KPI sentence', () => {
    const one = aggregateAdvertisers([f('@z', 'Q')]);
    const { container } = render(<AdvertisersOverview {...props({ rows: one, graph: buildGraph(one), kpis: kpis(one) })} />);
    expect(container.querySelector('.adv-figures')).toHaveTextContent('1 reklamodawca promuje 1 licencjonowaną firmę, w tym 0 powtarzających się');
  });

  it('shows the graph with the side table, or the full table', () => {
    const { rerender } = render(<AdvertisersOverview {...props()} />);
    expect(screen.getByRole('img', { name: /Graf powiązań/ })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Najczęstsi reklamodawcy' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Graf' })).toHaveAttribute('aria-pressed', 'true');
    rerender(<AdvertisersOverview {...props({ view: 'table' })} />);
    expect(screen.queryByRole('img', { name: /Graf powiązań/ })).toBeNull();
    expect(screen.getByRole('columnheader', { name: 'Promowane firmy' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Tabela' })).toHaveAttribute('aria-pressed', 'true');
  });

  it('reports filter and view changes', () => {
    const p = props();
    render(<AdvertisersOverview {...p} />);
    fireEvent.change(screen.getByLabelText('Okres'), { target: { value: '7' } });
    expect(p.onFiltersChange).toHaveBeenLastCalledWith({ period: '7' });
    fireEvent.change(screen.getByLabelText('Ryzyko'), { target: { value: 'high' } });
    expect(p.onFiltersChange).toHaveBeenLastCalledWith({ risk: 'high' });
    fireEvent.change(screen.getByLabelText('Minimalna liczba zgłoszeń'), { target: { value: '5' } });
    expect(p.onFiltersChange).toHaveBeenLastCalledWith({ minFindings: 5 });
    fireEvent.click(screen.getByLabelText('Tylko powtarzający się'));
    expect(p.onFiltersChange).toHaveBeenLastCalledWith({ repeatOnly: true });
    fireEvent.click(screen.getByRole('button', { name: 'Tabela' }));
    expect(p.onViewChange).toHaveBeenLastCalledWith('table');
  });

  it('states the findings it is based on and the cap', () => {
    render(<AdvertisersOverview {...props()} />);
    expect(screen.getByText('Przeanalizowane zgłoszenia M1: 11 z 11 (limit 600).')).toBeInTheDocument();
  });

  it('says older findings are left out when the cap cut the list', () => {
    render(<AdvertisersOverview {...props({ loaded: 600, total: 1000 })} />);
    expect(screen.getByText(/Przeanalizowane zgłoszenia M1: 600 z 1000 \(limit 600\)\. Starsze zgłoszenia pominięto\./)).toBeInTheDocument();
  });

  it('shows the loading, error and empty states, never partial data', () => {
    const { rerender } = render(<AdvertisersOverview {...props({ rows: undefined, graph: undefined, isLoading: true })} />);
    expect(screen.getByRole('status')).toHaveTextContent('Ładowanie');
    rerender(<AdvertisersOverview {...props({ rows: undefined, graph: undefined, isError: true })} />);
    expect(screen.getByRole('alert')).toHaveTextContent('Nie udało się pobrać danych o reklamodawcach.');
    expect(screen.queryByRole('table')).toBeNull();
    rerender(<AdvertisersOverview {...props({ rows: [], graph: buildGraph([]), kpis: kpis([]) })} />);
    expect(screen.getByRole('status')).toHaveTextContent('Brak reklamodawców dla wybranych filtrów');
    expect(screen.queryByRole('table')).toBeNull();
  });
});

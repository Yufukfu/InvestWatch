import { FINDINGS_CAP, type AdvertiserRow, type RelationNav } from '../model';
import type { AdvertiserFilters, AdvertiserKpis } from '../filters';
import { GRAPH_MAX_ADVERTISERS, type Graph } from '../graph';
import { AdvertiserFiltersBar, type AdvertiserView } from './AdvertiserFiltersBar';
import { AdvertiserGraph } from './AdvertiserGraph';
import { AdvertisersHero } from './AdvertisersHero';
import { AdvertisersTable } from './AdvertisersTable';
import { TopAdvertisers } from './TopAdvertisers';

type Props = RelationNav & {
  // Undefined while loading or after an error: the page never shows partial data.
  rows: AdvertiserRow[] | undefined;
  graph: Graph | undefined;
  kpis: AdvertiserKpis;
  loaded: number;
  total: number | undefined;
  isLoading: boolean;
  isError: boolean;
  filters: AdvertiserFilters;
  onFiltersChange: (patch: Partial<AdvertiserFilters>) => void;
  view: AdvertiserView;
  onViewChange: (view: AdvertiserView) => void;
  selected: string | undefined;
  onSelect: (key: string) => void;
};

// The Powiązania page (hen68's mockup, issue #72): KPI sentence, filters, then the graph with the side table
// or the full table.
export function AdvertisersOverview(props: Props) {
  const { rows, graph, kpis, loaded, total, isLoading, isError, filters, onFiltersChange, view, onViewChange, selected, onSelect, relationHref, onOpenRelation } = props;
  if (isError)
    return (
      <p className="state" role="alert">
        Nie udało się pobrać danych o reklamodawcach.
      </p>
    );
  if (isLoading || !rows || !graph)
    return (
      <p className="state" role="status">
        Ładowanie…
      </p>
    );
  const truncated = total !== undefined && total > loaded;
  return (
    <div className="adv-page">
      <AdvertisersHero kpis={kpis} />
      <AdvertiserFiltersBar filters={filters} onChange={onFiltersChange} view={view} onViewChange={onViewChange} />
      <p className="adv-note">
        {`Przeanalizowane zgłoszenia M1: ${loaded} z ${total ?? loaded} (limit ${FINDINGS_CAP}).`}
        {truncated && ' Starsze zgłoszenia pominięto.'}
      </p>
      {rows.length === 0 ? (
        <div className="state state-empty" role="status">
          <p className="state-title">Brak reklamodawców dla wybranych filtrów</p>
          <p className="state-hint">Zmień okres, poziom ryzyka lub minimalną liczbę zgłoszeń.</p>
        </div>
      ) : view === 'graph' ? (
        <div className="adv-layout">
          <AdvertiserGraph graph={graph} selected={selected} onOpenRelation={onOpenRelation} />
          <TopAdvertisers
            rows={rows.slice(0, GRAPH_MAX_ADVERTISERS)}
            matchedFindings={kpis.matchedFindings}
            selected={selected}
            onSelect={onSelect}
            relationHref={relationHref}
            onOpenRelation={onOpenRelation}
          />
        </div>
      ) : (
        <AdvertisersTable rows={rows} relationHref={relationHref} onOpenRelation={onOpenRelation} />
      )}
    </div>
  );
}

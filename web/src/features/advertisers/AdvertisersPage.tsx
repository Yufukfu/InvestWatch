import { useEffect, useMemo, useRef, useState } from 'react';
import { aggregateAdvertisers, relationFindings } from './aggregate';
import { AdvertisersOverview } from './components/AdvertisersOverview';
import type { AdvertiserView } from './components/AdvertiserFiltersBar';
import { RelationView } from './components/RelationView';
import { useAdvertisers } from './data/useAdvertisers';
import { useRelationNav } from './data/useRelationNav';
import { DEFAULT_ADVERTISER_FILTERS, filterFindings, filterRows, kpis as countKpis, type AdvertiserFilters } from './filters';
import { buildGraph } from './graph';

// Powiązania (M1, issue #72): who promotes which licensed firm, as a graph or a table, and the findings of one
// relation. Filters and the view are local UI state; the open relation is in the URL (useRelationNav).
export function AdvertisersPage() {
  const data = useAdvertisers();
  const nav = useRelationNav();
  const [filters, setFilters] = useState<AdvertiserFilters>(DEFAULT_ADVERTISER_FILTERS);
  const [view, setView] = useState<AdvertiserView>('graph');
  const [picked, setPicked] = useState<string | undefined>();
  // The period is measured from when the page opened, so a re-render does not shift it.
  const [now] = useState(() => Date.now());

  const filtered = useMemo(() => (data.findings ? filterFindings(data.findings, filters, now) : undefined), [data.findings, filters, now]);
  const grouped = useMemo(() => (filtered ? aggregateAdvertisers(filtered) : undefined), [filtered]);
  const rows = useMemo(() => (grouped ? filterRows(grouped, filters) : undefined), [grouped, filters]);
  const graph = useMemo(() => (rows ? buildGraph(rows) : undefined), [rows]);
  const kpis = useMemo(() => countKpis(rows ?? []), [rows]);
  // The side table's pick, else its first row (the mockup opens with the top advertiser highlighted).
  const selected = rows?.some((r) => r.key === picked) ? picked : rows?.[0]?.key;

  // Opening or leaving a relation starts at the top of the page.
  const relationKey = nav.relation ? `${nav.relation.advertiser}|${nav.relation.firm ?? ''}` : '';
  const shown = useRef(relationKey);
  useEffect(() => {
    if (shown.current === relationKey) return;
    shown.current = relationKey;
    window.scrollTo(0, 0);
  }, [relationKey]);

  if (nav.relation && filtered && grouped) {
    const { advertiser, firm } = nav.relation;
    return (
      <RelationView
        relation={nav.relation}
        row={grouped.find((r) => r.key === advertiser)}
        findings={relationFindings(filtered, advertiser, firm)}
        onBack={nav.closeRelation}
        onOpenFinding={nav.openFinding}
        relationHref={nav.relationHref}
        onOpenRelation={nav.onOpenRelation}
      />
    );
  }
  return (
    <AdvertisersOverview
      rows={rows}
      graph={graph}
      kpis={kpis}
      loaded={data.loaded}
      total={data.total}
      isLoading={data.isLoading}
      isError={data.isError}
      filters={filters}
      onFiltersChange={(patch) => setFilters((f) => ({ ...f, ...patch }))}
      view={view}
      onViewChange={setView}
      selected={selected}
      onSelect={setPicked}
      relationHref={nav.relationHref}
      onOpenRelation={nav.onOpenRelation}
    />
  );
}

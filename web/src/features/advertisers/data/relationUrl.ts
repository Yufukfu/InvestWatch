import type { Relation } from '../model';

// URL state of the relation page (#powiazania): `rel_adv` is the advertiser key, `rel_firm` the firm key
// (absent = every firm of that advertiser). Kept in the search string like the findings filters, so a
// shared link reopens the same relation and the browser back button returns to the graph.
export const REL_ADVERTISER = 'rel_adv';
export const REL_FIRM = 'rel_firm';


function toSearch(p: URLSearchParams): string {
  const s = p.toString().replaceAll('%2C', ',');
  return s ? `?${s}` : '';
}

export function parseRelation(search: string): Relation | undefined {
  const p = new URLSearchParams(search);
  const advertiser = p.get(REL_ADVERTISER)?.trim();
  if (!advertiser) return undefined;
  const firm = p.get(REL_FIRM)?.trim();
  return firm ? { advertiser, firm } : { advertiser };
}

// The search string with the relation set (or cleared with undefined); other parameters are kept.
export function relationSearch(search: string, relation: Relation | undefined): string {
  const p = new URLSearchParams(search);
  p.delete(REL_ADVERTISER);
  p.delete(REL_FIRM);
  if (relation) {
    p.set(REL_ADVERTISER, relation.advertiser);
    if (relation.firm) p.set(REL_FIRM, relation.firm);
  }
  return toSearch(p);
}

// Opening a finding goes to the findings page: the relation parameters are dropped, `finding` is set.
export function findingSearch(search: string, id: string): string {
  const p = new URLSearchParams(relationSearch(search, undefined));
  p.set('finding', id);
  return toSearch(p);
}

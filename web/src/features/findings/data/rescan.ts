import type { RescanView } from '../model';

// `document.scrape_meta` is an open object in the contract and carries scraped data, so `rescan`
// (derived by the api, issue #71) is read defensively: only a known state, a UUID id and a parseable
// time get through; anything else is dropped. `current` and a missing key (contract mock) mean no badge.
// `Date.parse` also takes loose strings such as "Nov 22"; the api sends ISO-8601 UTC times.
const ISO_TIME = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}/;
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

function isObject(v: unknown): v is Record<string, unknown> {
  return typeof v === 'object' && v !== null;
}

export function parseRescan(scrapeMeta: unknown): RescanView | undefined {
  if (!isObject(scrapeMeta)) return undefined;
  const rescan = scrapeMeta.rescan;
  if (!isObject(rescan)) return undefined;
  const { state, latest_document_id: id, checked_at: at } = rescan;
  if (state !== 'changed' && state !== 'removed') return undefined;
  const view: RescanView = { state };
  if (typeof id === 'string' && UUID.test(id)) view.latestDocumentId = id;
  if (typeof at === 'string' && ISO_TIME.test(at) && !Number.isNaN(Date.parse(at))) view.checkedAt = at;
  return view;
}

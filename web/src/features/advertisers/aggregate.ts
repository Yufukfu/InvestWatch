import { NO_FIRM, REPEAT_MIN_FINDINGS, REPEAT_MIN_FIRMS, type AdvertiserFinding, type AdvertiserRow, type PromotedFirm } from './model';

function clean(v: string | null | undefined): string | undefined {
  const t = v?.trim();
  return t ? t : undefined;
}

// Identity of an advertiser: handle, else profile URL, else website, else name (case-insensitive).
export function advertiserKey(a: NonNullable<AdvertiserFinding['advertiser']>): string | undefined {
  const handle = clean(a.handle);
  if (handle) return `h:${handle.toLowerCase()}`;
  const profile = clean(a.profileUrl);
  if (profile) return `p:${profile.toLowerCase()}`;
  const website = clean(a.website);
  if (website) return `w:${website.toLowerCase()}`;
  const name = clean(a.name);
  return name ? `n:${name.toLowerCase()}` : undefined;
}

export function firmKey(firm: AdvertiserFinding['firm']): { key: string; name?: string } {
  const name = clean(firm?.name);
  if (!firm || !name) return { key: NO_FIRM };
  const registryId = clean(firm.registryId);
  return { key: registryId ?? `name:${name.toLowerCase()}`, name };
}

const label = (r: AdvertiserRow) => r.name ?? r.handle ?? r.contact ?? r.key;

// The short label of an advertiser in the graph and the side table: the handle first, as in the mockup.
export const advertiserLabel = (r: Pick<AdvertiserRow, 'handle' | 'name' | 'contact' | 'key'>) => r.handle ?? r.name ?? r.contact ?? r.key;

// 2+ distinct matched firms, or 5+ findings (matched or not).
export function isRepeat(count: number, firms: readonly PromotedFirm[]): boolean {
  return count >= REPEAT_MIN_FINDINGS || firms.filter((f) => f.key !== NO_FIRM).length >= REPEAT_MIN_FIRMS;
}

// Groups M1 findings by advertiser and, inside each advertiser, by matched firm. Presentation only:
// it counts the findings the API returned and derives no score or risk level.
export function aggregateAdvertisers(findings: readonly AdvertiserFinding[]): AdvertiserRow[] {
  const seen = new Set<string>();
  const rows = new Map<string, AdvertiserRow & { firmMap: Map<string, PromotedFirm> }>();
  for (const f of findings) {
    if (f.module !== 'M1' || seen.has(f.id)) continue;
    seen.add(f.id);
    if (!f.advertiser) continue;
    const key = advertiserKey(f.advertiser);
    if (!key) continue;
    let row = rows.get(key);
    if (!row) {
      row = { key, count: 0, repeat: false, firms: [], firmMap: new Map() };
      rows.set(key, row);
    }
    row.count += 1;
    row.name ??= clean(f.advertiser.name);
    row.handle ??= clean(f.advertiser.handle);
    row.contact ??= clean(f.advertiser.profileUrl) ?? clean(f.advertiser.website);
    const fk = firmKey(f.firm);
    const firm = row.firmMap.get(fk.key);
    if (firm) firm.count += 1;
    else row.firmMap.set(fk.key, { key: fk.key, name: fk.name, count: 1 });
  }
  return [...rows.values()]
    .map(({ firmMap, ...row }) => ({
      ...row,
      repeat: isRepeat(row.count, [...firmMap.values()]),
      firms: [...firmMap.values()].sort(
        (a, b) => b.count - a.count || Number(a.key === NO_FIRM) - Number(b.key === NO_FIRM) || (a.name ?? '').localeCompare(b.name ?? '', 'pl'),
      ),
    }))
    .sort((a, b) => b.count - a.count || label(a).localeCompare(label(b), 'pl'));
}

// The findings of one advertiser, for one firm key (NO_FIRM = no matched firm) or for every firm when
// `firm` is undefined. M1 only, deduped by id, newest first (by `detectedAt`).
export function relationFindings(findings: readonly AdvertiserFinding[], advertiser: string, firm?: string): AdvertiserFinding[] {
  const seen = new Set<string>();
  const out: AdvertiserFinding[] = [];
  for (const f of findings) {
    if (f.module !== 'M1' || seen.has(f.id) || !f.advertiser) continue;
    seen.add(f.id);
    if (advertiserKey(f.advertiser) !== advertiser) continue;
    if (firm !== undefined && firmKey(f.firm).key !== firm) continue;
    out.push(f);
  }
  const time = (f: AdvertiserFinding) => {
    const t = Date.parse(f.detectedAt ?? '');
    return Number.isNaN(t) ? -Infinity : t;
  };
  return out.sort((a, b) => time(b) - time(a));
}

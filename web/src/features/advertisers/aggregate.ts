import { REPEAT_MIN, type AdvertiserFinding, type AdvertiserRow, type PromotedFirm } from './model';

const NO_FIRM = 'none';

function clean(v: string | null | undefined): string | undefined {
  const t = v?.trim();
  return t ? t : undefined;
}

// Identity of an advertiser: handle, else profile URL, else website, else name (case-insensitive).
function advertiserKey(a: NonNullable<AdvertiserFinding['advertiser']>): string | undefined {
  const handle = clean(a.handle);
  if (handle) return `h:${handle.toLowerCase()}`;
  const profile = clean(a.profileUrl);
  if (profile) return `p:${profile.toLowerCase()}`;
  const website = clean(a.website);
  if (website) return `w:${website.toLowerCase()}`;
  const name = clean(a.name);
  return name ? `n:${name.toLowerCase()}` : undefined;
}

function firmKey(firm: AdvertiserFinding['firm']): { key: string; name?: string } {
  const name = clean(firm?.name);
  if (!firm || !name) return { key: NO_FIRM };
  const registryId = clean(firm.registryId);
  return { key: registryId ?? `name:${name.toLowerCase()}`, name };
}

const label = (r: AdvertiserRow) => r.name ?? r.handle ?? r.contact ?? r.key;

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
      repeat: row.count >= REPEAT_MIN,
      firms: [...firmMap.values()].sort(
        (a, b) => b.count - a.count || Number(a.key === NO_FIRM) - Number(b.key === NO_FIRM) || (a.name ?? '').localeCompare(b.name ?? '', 'pl'),
      ),
    }))
    .sort((a, b) => b.count - a.count || label(a).localeCompare(label(b), 'pl'));
}

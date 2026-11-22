import type { FindingModule, FindingPlatform, FindingStatus, RegistryType, RiskLevel, RuleMethod, Severity } from '../model';

// Polish labels shared by the findings components. Values (ids, enums) are shown as the API returns them.
export const STATUS_LABEL: Record<FindingStatus, string> = {
  new: 'Nowe',
  in_review: 'W analizie',
  confirmed: 'Potwierdzone',
  false_positive: 'Fałszywy alarm',
  closed: 'Zamknięte',
};

export const RISK_LABEL: Record<RiskLevel, string> = { high: 'Wysoki', medium: 'Średni', low: 'Niski' };

export const MODULE_LABEL: Record<FindingModule, string> = {
  M1: 'Finfluencerzy',
  M2: 'Zgodność reklam',
  M3: 'Usługi bez zezwolenia',
};

export const PLATFORM_LABEL: Record<FindingPlatform, string> = {
  web: 'Strona WWW',
  facebook: 'Facebook',
  instagram: 'Instagram',
  tiktok: 'TikTok',
  youtube: 'YouTube',
  x: 'X',
  forum: 'Forum',
  other: 'Inna',
};

export function platformLabel(p: string): string {
  return (PLATFORM_LABEL as Record<string, string>)[p] ?? p;
}

const UTC = new Intl.DateTimeFormat('pl-PL', {
  day: '2-digit',
  month: '2-digit',
  year: 'numeric',
  hour: '2-digit',
  minute: '2-digit',
  timeZone: 'UTC',
});

export function formatUtc(iso: string): string {
  const t = Date.parse(iso);
  return Number.isNaN(t) ? iso : `${UTC.format(t)} UTC`;
}

// The table's detection time: UTC, day.month.year · hour:minute (the table header says what it is, the hover says UTC).
export function formatDetected(iso: string): string {
  const t = Date.parse(iso);
  if (Number.isNaN(t)) return iso;
  const d = new Date(t);
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${pad(d.getUTCDate())}.${pad(d.getUTCMonth() + 1)}.${d.getUTCFullYear()} · ${pad(d.getUTCHours())}:${pad(d.getUTCMinutes())}`;
}

// Polish plural: 1 zgłoszenie, 2-4 zgłoszenia (not 12-14), otherwise zgłoszeń.
export function findingsCount(n: number): string {
  const lastTwo = n % 100;
  const last = n % 10;
  if (n === 1) return '1 zgłoszenie';
  if (last >= 2 && last <= 4 && (lastTwo < 12 || lastTwo > 14)) return `${n} zgłoszenia`;
  return `${n} zgłoszeń`;
}

export const SEVERITY_LABEL: Record<Severity, string> = { high: 'wysoka', medium: 'średnia', low: 'niska' };

export const METHOD_LABEL: Record<RuleMethod, string> = { rule: 'reguła', llm: 'model językowy', hybrid: 'reguła + model językowy' };

export const REGISTRY_LABEL: Record<RegistryType, string> = {
  brokerage_house: 'dom maklerski',
  brokerage_bank: 'bank prowadzący działalność maklerską',
  foreign_branch: 'oddział firmy zagranicznej',
  foreign_no_branch: 'firma zagraniczna bez oddziału',
};

// Only http(s) links from scraped data become anchors; anything else is shown as text.
export function safeHttpUrl(url: string | null | undefined): string | undefined {
  if (!url) return undefined;
  try {
    const u = new URL(url);
    return u.protocol === 'https:' || u.protocol === 'http:' ? u.href : undefined;
  } catch {
    return undefined;
  }
}

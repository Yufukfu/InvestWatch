import type { FindingModule, FindingPlatform, FindingStatus, RiskLevel } from '../model';

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

// Polish plural: 1 zgłoszenie, 2-4 zgłoszenia (not 12-14), otherwise zgłoszeń.
export function findingsCount(n: number): string {
  const lastTwo = n % 100;
  const last = n % 10;
  if (n === 1) return '1 zgłoszenie';
  if (last >= 2 && last <= 4 && (lastTwo < 12 || lastTwo > 14)) return `${n} zgłoszenia`;
  return `${n} zgłoszeń`;
}

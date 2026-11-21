import type { GetFindingsApiArg } from '../../../api/generated';
import {
  MODULES,
  PAGE_SIZES,
  PLATFORMS,
  RISK_LEVELS,
  SORTS,
  STATUSES,
  type FindingFilters,
} from '../model';

// URL <-> filter state. Parameter names are those of GET /findings in contracts/openapi.yaml, so a
// shared link reproduces the view. Every value is validated against the contract enums; an invalid
// one is dropped (the default applies) and never sent to the backend.

export const DEFAULT_FILTERS: FindingFilters = { status: [], sort: '-detected_at', page: 1, pageSize: 25 };

const DAY = /^\d{4}-\d{2}-\d{2}$/;
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

function oneOf<T extends string>(values: readonly T[], v: string | null): T | undefined {
  return v !== null && (values as readonly string[]).includes(v) ? (v as T) : undefined;
}

function positiveInt(v: string | null): number | undefined {
  if (v === null || !/^\d+$/.test(v)) return undefined;
  const n = Number(v);
  return n >= 1 ? n : undefined;
}

function day(v: string | null): string | undefined {
  return v !== null && DAY.test(v) && !Number.isNaN(Date.parse(`${v}T00:00:00Z`)) ? v : undefined;
}

export function parseFilters(search: string): FindingFilters {
  const p = new URLSearchParams(search);
  const score = p.get('score_min');
  const scoreMin = score !== null && score.trim() !== '' ? Number(score) : NaN;
  const pageSize = positiveInt(p.get('page_size'));
  const q = p.get('q')?.trim();
  return {
    module: oneOf(MODULES, p.get('module')),
    status: (p.get('status') ?? '')
      .split(',')
      .map((s) => oneOf(STATUSES, s))
      .filter((s) => s !== undefined),
    riskLevel: oneOf(RISK_LEVELS, p.get('risk_level')),
    platform: oneOf(PLATFORMS, p.get('platform')),
    scoreMin: scoreMin >= 0 && scoreMin <= 1 ? scoreMin : undefined,
    dateFrom: day(p.get('date_from')),
    dateTo: day(p.get('date_to')),
    q: q ? q : undefined,
    sort: oneOf(SORTS, p.get('sort')) ?? DEFAULT_FILTERS.sort,
    page: positiveInt(p.get('page')) ?? DEFAULT_FILTERS.page,
    pageSize: pageSize !== undefined && PAGE_SIZES.includes(pageSize) ? pageSize : DEFAULT_FILTERS.pageSize,
  };
}

export function parseSelected(search: string): string | undefined {
  const id = new URLSearchParams(search).get('finding');
  return id !== null && UUID.test(id) ? id : undefined;
}

// Defaults are omitted, so the unfiltered view has a clean URL.
export function serializeUrl(f: FindingFilters, selected: string | undefined): string {
  const p = new URLSearchParams();
  if (f.module) p.set('module', f.module);
  if (f.status.length) p.set('status', f.status.join(','));
  if (f.riskLevel) p.set('risk_level', f.riskLevel);
  if (f.platform) p.set('platform', f.platform);
  if (f.scoreMin !== undefined) p.set('score_min', String(f.scoreMin));
  if (f.dateFrom) p.set('date_from', f.dateFrom);
  if (f.dateTo) p.set('date_to', f.dateTo);
  if (f.q) p.set('q', f.q);
  if (f.sort !== DEFAULT_FILTERS.sort) p.set('sort', f.sort);
  if (f.page !== DEFAULT_FILTERS.page) p.set('page', String(f.page));
  if (f.pageSize !== DEFAULT_FILTERS.pageSize) p.set('page_size', String(f.pageSize));
  if (selected) p.set('finding', selected);
  const s = p.toString().replaceAll('%2C', ',');
  return s ? `?${s}` : '';
}

// Any change other than an explicit page change starts again from page 1.
export function withFilter(f: FindingFilters, patch: Partial<FindingFilters>): FindingFilters {
  return { ...f, ...patch, page: patch.page ?? 1 };
}

export function toQueryArg(f: FindingFilters): GetFindingsApiArg {
  const arg: GetFindingsApiArg = { sort: f.sort, page: f.page, pageSize: f.pageSize };
  if (f.module) arg.module = f.module;
  if (f.status.length) arg.status = f.status.join(',');
  if (f.riskLevel) arg.riskLevel = f.riskLevel;
  if (f.platform) arg.platform = f.platform;
  if (f.scoreMin !== undefined) arg.scoreMin = f.scoreMin;
  if (f.dateFrom) arg.dateFrom = `${f.dateFrom}T00:00:00Z`;
  if (f.dateTo) arg.dateTo = `${f.dateTo}T23:59:59Z`;
  if (f.q) arg.q = f.q;
  return arg;
}

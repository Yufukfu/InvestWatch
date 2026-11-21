// App-owned view models for the findings workspace. Components depend on these, not on the generated
// DTOs, so a change of the API client or of unused DTO fields does not reach them (ADR 0204).
export type FindingModule = 'M1' | 'M2' | 'M3';
export type FindingStatus = 'new' | 'in_review' | 'confirmed' | 'false_positive' | 'closed';
export type RiskLevel = 'high' | 'medium' | 'low';
export type FindingPlatform = 'web' | 'facebook' | 'instagram' | 'tiktok' | 'youtube' | 'x' | 'forum' | 'other';
export type FindingSort = '-detected_at' | 'detected_at' | '-score' | 'score';

export const MODULES: readonly FindingModule[] = ['M1', 'M2', 'M3'];
export const STATUSES: readonly FindingStatus[] = ['new', 'in_review', 'confirmed', 'false_positive', 'closed'];
export const RISK_LEVELS: readonly RiskLevel[] = ['high', 'medium', 'low'];
export const PLATFORMS: readonly FindingPlatform[] = ['web', 'facebook', 'instagram', 'tiktok', 'youtube', 'x', 'forum', 'other'];
export const SORTS: readonly FindingSort[] = ['-detected_at', 'detected_at', '-score', 'score'];
export const PAGE_SIZES: readonly number[] = [10, 25, 50, 100];

// Filters, sort and paging of GET /findings. Dates are calendar days (YYYY-MM-DD, UTC).
export type FindingFilters = {
  module?: FindingModule;
  status: FindingStatus[];
  riskLevel?: RiskLevel;
  platform?: FindingPlatform;
  scoreMin?: number;
  dateFrom?: string;
  dateTo?: string;
  q?: string;
  sort: FindingSort;
  page: number;
  pageSize: number;
};

export type FindingRow = {
  id: string;
  module: FindingModule;
  title: string;
  platform: string;
  score: number;
  // Optional in the contract (present in API responses only); undefined renders as "no data".
  riskLevel?: RiskLevel;
  status: FindingStatus;
  detectedAt: string;
};

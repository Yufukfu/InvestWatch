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

export type RuleOutcome = 'fail' | 'pass' | 'not_applicable' | 'uncertain';
export type Severity = 'high' | 'medium' | 'low';
export type RuleMethod = 'rule' | 'llm' | 'hybrid';
export type RegistryType = 'brokerage_house' | 'brokerage_bank' | 'foreign_branch' | 'foreign_no_branch';

// One rule (M2) or signal (M1/M3) result; ids and names are shown exactly as the API returns them.
export type RuleView = {
  ruleId: string;
  name: string;
  result: RuleOutcome;
  severity: Severity;
  evidence?: string | null;
  explanation?: string | null;
  legalBasis?: string | null;
  method?: RuleMethod | null;
};

export type FirmView = {
  name: string;
  authorized?: boolean;
  registryType?: RegistryType | null;
  matchConfidence?: number;
};

export type AdvertiserView = {
  name?: string | null;
  handle?: string | null;
  profileUrl?: string | null;
  website?: string | null;
  inRegistry?: boolean;
  onWarningList?: boolean | null;
};

// Re-scan state of the finding's page (issue #71); `current` is not represented, it shows nothing.
export type RescanState = 'changed' | 'removed';
export type RescanView = { state: RescanState; latestDocumentId?: string; checkedAt?: string };

export type FindingDetail = {
  id: string;
  module: FindingModule;
  title: string;
  summary?: string | null;
  score: number;
  riskLevel?: RiskLevel;
  status: FindingStatus;
  note?: string | null;
  url: string;
  platform: string;
  detectedAt: string;
  firm?: FirmView;
  advertiser?: AdvertiserView;
  rules: RuleView[];
  excerpt?: string | null;
  documentText?: string;
  screenshotUrl?: string;
  pipelineVersion?: string;
  llm?: string | null;
  // Printable evidence pack (GET /findings/{id}/export?format=html) under the app's API base.
  exportUrl?: string;
  rescan?: RescanView;
};

// App-owned view models for the advertiser-to-firm table (M1). Components depend on these, not on the
// generated DTOs (ADR 0204).

// One M1 finding reduced to what the grouping needs.
export type AdvertiserFinding = {
  id: string;
  module: string;
  advertiser?: {
    name?: string | null;
    handle?: string | null;
    profileUrl?: string | null;
    website?: string | null;
  } | null;
  firm?: { name: string; registryId?: string | null } | null;
  // Shown on the relation page and used by the client-side filters; optional so grouping tests stay small.
  title?: string;
  platform?: string;
  score?: number;
  riskLevel?: RiskLevel;
  detectedAt?: string;
};

export type RiskLevel = 'high' | 'medium' | 'low';

// A firm the advertiser promotes; `name` undefined = findings with no matched firm.
export type PromotedFirm = { key: string; name?: string; count: number };

export type AdvertiserRow = {
  key: string;
  name?: string;
  handle?: string;
  // Profile URL, else website: shown as plain text when there is no name and no handle.
  contact?: string;
  count: number;
  repeat: boolean;
  firms: PromotedFirm[];
};

// Paging cap of the section: at most MAX_PAGES pages of PAGE_SIZE findings.
export const PAGE_SIZE = 200;
export const MAX_PAGES = 3;
export const FINDINGS_CAP = PAGE_SIZE * MAX_PAGES;
// A repeat advertiser promotes at least REPEAT_MIN_FIRMS distinct matched firms or has at least
// REPEAT_MIN_FINDINGS findings (hen68's mockup, issue #72).
export const REPEAT_MIN_FIRMS = 2;
export const REPEAT_MIN_FINDINGS = 5;
// Firm key of findings with no matched firm.
export const NO_FIRM = 'none';

export type AdvertisersView = {
  rows: AdvertiserRow[] | undefined;
  // The M1 findings behind `rows` (deduped), for the client-side filters and the relation page.
  findings: AdvertiserFinding[] | undefined;
  // Findings received (before grouping) and the `total` the API reported.
  loaded: number;
  total: number | undefined;
  isLoading: boolean;
  isError: boolean;
};

// The relation page: one advertiser (key) and one firm key, or every firm of the advertiser when `firm` is absent.
export type Relation = { advertiser: string; firm?: string };

// Callbacks the presentational components get from the page to move between the graph and a relation.
export type RelationNav = {
  // The href of a relation, so links work with a middle click and show the target.
  relationHref: (relation: Relation) => string;
  onOpenRelation: (relation: Relation) => void;
};

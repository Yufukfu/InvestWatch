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
};

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
// An advertiser with at least this many findings is a repeat advertiser.
export const REPEAT_MIN = 2;

export type AdvertisersView = {
  rows: AdvertiserRow[] | undefined;
  // Findings received (before grouping) and the `total` the API reported.
  loaded: number;
  total: number | undefined;
  isLoading: boolean;
  isError: boolean;
};

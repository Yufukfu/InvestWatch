import { baseApi as api } from "./baseApi";
export const addTagTypes = [
  "findings",
  "stats",
  "calibration",
  "settings",
  "sources",
  "documents",
  "system",
] as const;
const injectedRtkApi = api
  .enhanceEndpoints({
    addTagTypes,
  })
  .injectEndpoints({
    endpoints: (build) => ({
      getFindings: build.query<GetFindingsApiResponse, GetFindingsApiArg>({
        query: (queryArg) => ({
          url: `/findings`,
          params: {
            module: queryArg["module"],
            status: queryArg.status,
            platform: queryArg.platform,
            source_id: queryArg.sourceId,
            risk_level: queryArg.riskLevel,
            score_min: queryArg.scoreMin,
            date_from: queryArg.dateFrom,
            date_to: queryArg.dateTo,
            q: queryArg.q,
            sort: queryArg.sort,
            page: queryArg.page,
            page_size: queryArg.pageSize,
          },
        }),
        providesTags: ["findings"],
      }),
      getFindingsById: build.query<
        GetFindingsByIdApiResponse,
        GetFindingsByIdApiArg
      >({
        query: (queryArg) => ({ url: `/findings/${queryArg.id}` }),
        providesTags: ["findings"],
      }),
      patchFindingsById: build.mutation<
        PatchFindingsByIdApiResponse,
        PatchFindingsByIdApiArg
      >({
        query: (queryArg) => ({
          url: `/findings/${queryArg.id}`,
          method: "PATCH",
          body: queryArg.body,
        }),
        invalidatesTags: ["findings"],
      }),
      getStatsTrend: build.query<GetStatsTrendApiResponse, GetStatsTrendApiArg>(
        {
          query: (queryArg) => ({
            url: `/stats/trend`,
            params: {
              module: queryArg["module"],
              bucket: queryArg.bucket,
              risk_level: queryArg.riskLevel,
              date_from: queryArg.dateFrom,
              date_to: queryArg.dateTo,
            },
          }),
          providesTags: ["stats"],
        },
      ),
      getStatsSummary: build.query<
        GetStatsSummaryApiResponse,
        GetStatsSummaryApiArg
      >({
        query: () => ({ url: `/stats/summary` }),
        providesTags: ["stats"],
      }),
      getCalibration: build.query<
        GetCalibrationApiResponse,
        GetCalibrationApiArg
      >({
        query: (queryArg) => ({
          url: `/calibration`,
          params: {
            module: queryArg["module"],
          },
        }),
        providesTags: ["calibration"],
      }),
      getSettingsThresholds: build.query<
        GetSettingsThresholdsApiResponse,
        GetSettingsThresholdsApiArg
      >({
        query: () => ({ url: `/settings/thresholds` }),
        providesTags: ["settings"],
      }),
      putSettingsThresholds: build.mutation<
        PutSettingsThresholdsApiResponse,
        PutSettingsThresholdsApiArg
      >({
        query: (queryArg) => ({
          url: `/settings/thresholds`,
          method: "PUT",
          body: queryArg.thresholds,
        }),
        invalidatesTags: ["settings"],
      }),
      getSources: build.query<GetSourcesApiResponse, GetSourcesApiArg>({
        query: () => ({ url: `/sources` }),
        providesTags: ["sources"],
      }),
      postSources: build.mutation<PostSourcesApiResponse, PostSourcesApiArg>({
        query: (queryArg) => ({
          url: `/sources`,
          method: "POST",
          body: queryArg.sourceInput,
        }),
        invalidatesTags: ["sources"],
      }),
      patchSourcesById: build.mutation<
        PatchSourcesByIdApiResponse,
        PatchSourcesByIdApiArg
      >({
        query: (queryArg) => ({
          url: `/sources/${queryArg.id}`,
          method: "PATCH",
          body: queryArg.sourceInput,
        }),
        invalidatesTags: ["sources"],
      }),
      postScans: build.mutation<PostScansApiResponse, PostScansApiArg>({
        query: (queryArg) => ({
          url: `/scans`,
          method: "POST",
          body: queryArg.body,
        }),
        invalidatesTags: ["sources"],
      }),
      getDocumentsByIdScreenshotAndViewport: build.query<
        GetDocumentsByIdScreenshotAndViewportApiResponse,
        GetDocumentsByIdScreenshotAndViewportApiArg
      >({
        query: (queryArg) => ({
          url: `/documents/${queryArg.id}/screenshot/${queryArg.viewport}`,
        }),
        providesTags: ["documents"],
      }),
      getHealth: build.query<GetHealthApiResponse, GetHealthApiArg>({
        query: () => ({ url: `/health` }),
        providesTags: ["system"],
      }),
    }),
    overrideExisting: false,
  });
export { injectedRtkApi as investWatchApi };
export type GetFindingsApiResponse =
  /** status 200 Page of findings (mock `mocks/findings.json`) */ {
    items: Finding[];
    total: number;
    page: number;
    page_size: number;
  };
export type GetFindingsApiArg = {
  module?: "M1" | "M2" | "M3";
  /** Comma-separated list */
  status?: string;
  platform?: string;
  sourceId?: string;
  riskLevel?: "high" | "medium" | "low";
  scoreMin?: number;
  dateFrom?: string;
  dateTo?: string;
  /** Full-text search in title */
  q?: string;
  sort?: "detected_at" | "-detected_at" | "score" | "-score";
  page?: number;
  pageSize?: number;
};
export type GetFindingsByIdApiResponse =
  /** status 200 Mock `mocks/finding-detail.json` */ Finding & {
    /** A single piece of content collected by the scraper. Stored in the `documents` table (simple columns + JSONB payload). Produced by the scraper, consumed by analytics and the API. */
    document?: {
      id: Uuid2;
      /** Row in the `sources` table; null for ad-hoc URLs. */
      source_id?: Uuid2 | null;
      platform: Platform;
      /** firm_own = published by the investment firm itself (M2); third_party = published by someone else (M1/M3). */
      source_kind: "firm_own" | "third_party" | "unknown";
      url: string;
      canonical_url?: string | null;
      fetched_at: string;
      published_at?: string | null;
      http_status?: number | null;
      /** ISO 639-1 code if known; analytics detects it anyway. */
      lang?: string | null;
      title?: string | null;
      /** Clean text of the whole material (no HTML). */
      text: string;
      /** sha256 of the normalized text, for deduplication. */
      content_hash?: string | null;
      author?: {
        name?: string | null;
        handle?: string | null;
        profile_url?: string | null;
        followers?: number | null;
      } | null;
      links?: {
        href: string;
        text?: string | null;
        /** Raw rel attribute, e.g. 'nofollow sponsored'. */
        rel?: string | null;
      }[];
      media?: {
        type: "image" | "video";
        /** Key in the MinIO bucket `iw-raw`, e.g. media/{document_id}/0.jpg */
        object_key: string;
        alt?: string | null;
        /** Filled by analytics if OCR is run. */
        ocr_text?: string | null;
      }[];
      /** html/{document_id}.html in MinIO. */
      html_object_key?: string | null;
      screenshots?: {
        desktop?: string | null;
        tablet?: string | null;
        mobile?: string | null;
      } | null;
      /** Rendered text blocks from Playwright. Needed only for the visual M2 rules (R4-R8, R13); empty for social media posts. */
      blocks?: Block[];
      scrape_meta?:
        | {
            scraper?: "playwright" | "httpx" | "api" | "manual";
            user_agent?: string | null;
            /** Proxy identifier, never credentials. */
            proxy?: string | null;
            duration_ms?: number | null;
            [key: string]: any;
          }
        | {
            [key: string]: any;
          };
    };
    /** API URLs for the screenshots, keyed by viewport */
    screenshot_urls?: {
      [key: string]: string;
    };
  };
export type GetFindingsByIdApiArg = {
  id: string;
};
export type PatchFindingsByIdApiResponse = /** status 200 Updated finding */ {
  id: Uuid;
  document_id: Uuid;
  module: Module;
  /** Raw score; higher = more likely a violation. */
  score: number;
  /** Present only in API responses: high >= threshold, medium >= threshold - 0.2, otherwise low. */
  risk_level?: "high" | "medium" | "low";
  status: Status;
  /** Short user-facing title (Polish). */
  title: string;
  /** 2-3 sentence user-facing rationale (Polish). */
  summary?: string | null;
  /** Investment firm the material concerns (M1, M2). */
  firm?: {
    name: string;
    registry_id?: Uuid | null;
    registry_type?:
      | (
          | "brokerage_house"
          | "brokerage_bank"
          | "foreign_branch"
          | "foreign_no_branch"
          | null
        )
      | (
          | "brokerage_house"
          | "brokerage_bank"
          | "foreign_branch"
          | "foreign_no_branch"
          | null
        );
    authorized?: boolean;
    match_confidence?: number;
  } | null;
  /** Party publishing or offering the content (M1, M3). */
  advertiser?: {
    name?: string | null;
    handle?: string | null;
    profile_url?: string | null;
    website?: string | null;
    in_registry?: boolean;
    /** Entity appears on the KNF public warnings list. */
    on_warning_list?: boolean | null;
  } | null;
  /** M2: results of the 18 UKNF rules (R1-R18); M1/M3: signals (S1.x / S3.x). */
  rules: RuleResult[];
  content_excerpt?: string | null;
  url: string;
  platform:
    | "web"
    | "facebook"
    | "instagram"
    | "tiktok"
    | "youtube"
    | "x"
    | "forum"
    | "other";
  /** Analyst note set via PATCH. */
  note?: string | null;
  detected_at: string;
  updated_at: string;
  model?: {
    pipeline_version?: string;
    /** null = rules-only mode (LLM unavailable). */
    llm?: string | null;
    embedder?: string | null;
  } | null;
};
export type PatchFindingsByIdApiArg = {
  id: string;
  body: {
    status?: "new" | "in_review" | "confirmed" | "false_positive" | "closed";
    note?: string | null;
  };
};
export type GetStatsTrendApiResponse =
  /** status 200 Mock `mocks/trend.json` */ {
    bucket: "hour" | "day";
    points: {
      t: string;
      M1: number;
      M2: number;
      M3: number;
    }[];
  };
export type GetStatsTrendApiArg = {
  module?: "M1" | "M2" | "M3";
  bucket?: "hour" | "day";
  riskLevel?: "high" | "medium" | "low";
  dateFrom?: string;
  dateTo?: string;
};
export type GetStatsSummaryApiResponse =
  /** status 200 Mock `mocks/summary.json` */ {
    total: number;
    by_module: {
      [key: string]: number;
    };
    by_status: {
      [key: string]: number;
    };
    by_platform: {
      [key: string]: number;
    };
    by_risk_level: {
      [key: string]: number;
    };
    last_scan_at?: string | null;
  };
export type GetStatsSummaryApiArg = void;
export type GetCalibrationApiResponse =
  /** status 200 Mock `mocks/calibration-M2.json` */ {
    module: "M1" | "M2" | "M3";
    current_threshold: number;
    labeled_samples: number;
    points: {
      threshold: number;
      tp: number;
      fp: number;
      fn: number;
      tn: number;
      precision: number;
      recall: number;
      f1?: number;
    }[];
  };
export type GetCalibrationApiArg = {
  module: "M1" | "M2" | "M3";
};
export type GetSettingsThresholdsApiResponse =
  /** status 200 Mock `mocks/thresholds.json` */ Thresholds;
export type GetSettingsThresholdsApiArg = void;
export type PutSettingsThresholdsApiResponse =
  /** status 200 Saved thresholds */ Thresholds;
export type PutSettingsThresholdsApiArg = {
  thresholds: Thresholds;
};
export type GetSourcesApiResponse =
  /** status 200 Mock `mocks/sources.json` */ {
    items: Source[];
  };
export type GetSourcesApiArg = void;
export type PostSourcesApiResponse = /** status 201 Created source */ {
  id: string;
  name: string;
  platform:
    | "web"
    | "facebook"
    | "instagram"
    | "tiktok"
    | "youtube"
    | "x"
    | "forum"
    | "other";
  /** Start URL, profile URL or search query URL. */
  url: string;
  source_kind: "firm_own" | "third_party" | "unknown";
  target_modules: ("M1" | "M2" | "M3")[];
  /** Cron expression, e.g. '0 *\/6 * * *'; null = manual only. */
  schedule_cron?: string | null;
  active: boolean;
  last_run_at?: string | null;
  last_run_status?:
    | ("ok" | "partial" | "failed" | "running" | null)
    | ("ok" | "partial" | "failed" | "running" | null);
  documents_count?: number | null;
};
export type PostSourcesApiArg = {
  sourceInput: SourceInput;
};
export type PatchSourcesByIdApiResponse =
  /** status 200 Updated source */ Source;
export type PatchSourcesByIdApiArg = {
  id: string;
  sourceInput: SourceInput;
};
export type PostScansApiResponse = /** status 202 Scan queued */ {
  queued?: boolean;
  source_id?: string;
};
export type PostScansApiArg = {
  body: {
    source_id: string;
  };
};
export type GetDocumentsByIdScreenshotAndViewportApiResponse =
  /** status 200 PNG image */ Blob;
export type GetDocumentsByIdScreenshotAndViewportApiArg = {
  id: string;
  viewport: "desktop" | "tablet" | "mobile";
};
export type GetHealthApiResponse = /** status 200 Mock `mocks/health.json` */ {
  status: "ok" | "degraded" | "down";
  services: {
    [key: string]: "ok" | "degraded" | "down";
  };
};
export type GetHealthApiArg = void;
export type Uuid = string;
export type Module = "M1" | "M2" | "M3";
export type Status =
  "new" | "in_review" | "confirmed" | "false_positive" | "closed";
export type RuleResult = {
  /** R1-R18 (incl. R12a/R12b) for M2, S1.x for M1, S3.x for M3. */
  rule_id: string;
  name: string;
  /** For M1/M3 signals: fail = signal detected (suspicious). */
  result: "fail" | "pass" | "not_applicable" | "uncertain";
  severity: "high" | "medium" | "low";
  /** Exact quote from the document (verified substring). */
  evidence?: string | null;
  evidence_locator?: {
    viewport?:
      | ("desktop" | "tablet" | "mobile" | null)
      | ("desktop" | "tablet" | "mobile" | null);
    bbox?: number[] | null;
  } | null;
  /** User-facing (Polish). */
  explanation?: string | null;
  legal_basis?: string | null;
  method?:
    ("rule" | "llm" | "hybrid" | null) | ("rule" | "llm" | "hybrid" | null);
};
export type Finding = {
  id: Uuid;
  document_id: Uuid;
  module: Module;
  /** Raw score; higher = more likely a violation. */
  score: number;
  /** Present only in API responses: high >= threshold, medium >= threshold - 0.2, otherwise low. */
  risk_level?: "high" | "medium" | "low";
  status: Status;
  /** Short user-facing title (Polish). */
  title: string;
  /** 2-3 sentence user-facing rationale (Polish). */
  summary?: string | null;
  /** Investment firm the material concerns (M1, M2). */
  firm?: {
    name: string;
    registry_id?: Uuid | null;
    registry_type?:
      | (
          | "brokerage_house"
          | "brokerage_bank"
          | "foreign_branch"
          | "foreign_no_branch"
          | null
        )
      | (
          | "brokerage_house"
          | "brokerage_bank"
          | "foreign_branch"
          | "foreign_no_branch"
          | null
        );
    authorized?: boolean;
    match_confidence?: number;
  } | null;
  /** Party publishing or offering the content (M1, M3). */
  advertiser?: {
    name?: string | null;
    handle?: string | null;
    profile_url?: string | null;
    website?: string | null;
    in_registry?: boolean;
    /** Entity appears on the KNF public warnings list. */
    on_warning_list?: boolean | null;
  } | null;
  /** M2: results of the 18 UKNF rules (R1-R18); M1/M3: signals (S1.x / S3.x). */
  rules: RuleResult[];
  content_excerpt?: string | null;
  url: string;
  platform:
    | "web"
    | "facebook"
    | "instagram"
    | "tiktok"
    | "youtube"
    | "x"
    | "forum"
    | "other";
  /** Analyst note set via PATCH. */
  note?: string | null;
  detected_at: string;
  updated_at: string;
  model?: {
    pipeline_version?: string;
    /** null = rules-only mode (LLM unavailable). */
    llm?: string | null;
    embedder?: string | null;
  } | null;
};
export type Uuid2 = string;
export type Platform =
  | "web"
  | "facebook"
  | "instagram"
  | "tiktok"
  | "youtube"
  | "x"
  | "forum"
  | "other";
export type Block = {
  viewport: "desktop" | "tablet" | "mobile";
  text: string;
  tag?: string | null;
  font_size_px: number;
  font_weight?: number | null;
  color?: string | null;
  background_color?: string | null;
  /** [x, y, width, height] in CSS pixels relative to the page. */
  bbox?: number[] | null;
  /** Rendered and not hidden by display/visibility/opacity/zero size. */
  visible: boolean;
  /** Visible without scrolling. */
  in_viewport_on_load?: boolean | null;
  /** Hidden behind <details>, accordion, tooltip, modal or a link. */
  requires_interaction?: boolean | null;
  region?:
    | ("main" | "header" | "footer" | "legal" | "aside" | "overlay" | null)
    | ("main" | "header" | "footer" | "legal" | "aside" | "overlay" | null);
  /** Text is cut off at this viewport. */
  overflow_clipped?: boolean | null;
};
export type Error = {
  error: string;
  details?: any;
};
export type Thresholds = {
  M1: number;
  M2: number;
  M3: number;
};
export type Source = {
  id: string;
  name: string;
  platform:
    | "web"
    | "facebook"
    | "instagram"
    | "tiktok"
    | "youtube"
    | "x"
    | "forum"
    | "other";
  /** Start URL, profile URL or search query URL. */
  url: string;
  source_kind: "firm_own" | "third_party" | "unknown";
  target_modules: ("M1" | "M2" | "M3")[];
  /** Cron expression, e.g. '0 *\/6 * * *'; null = manual only. */
  schedule_cron?: string | null;
  active: boolean;
  last_run_at?: string | null;
  last_run_status?:
    | ("ok" | "partial" | "failed" | "running" | null)
    | ("ok" | "partial" | "failed" | "running" | null);
  documents_count?: number | null;
};
export type SourceInput = {
  name?: string;
  platform?:
    | "web"
    | "facebook"
    | "instagram"
    | "tiktok"
    | "youtube"
    | "x"
    | "forum"
    | "other";
  url?: string;
  source_kind?: "firm_own" | "third_party" | "unknown";
  target_modules?: ("M1" | "M2" | "M3")[];
  schedule_cron?: string | null;
  active?: boolean;
};
export const {
  useGetFindingsQuery,
  useLazyGetFindingsQuery,
  useGetFindingsByIdQuery,
  useLazyGetFindingsByIdQuery,
  usePatchFindingsByIdMutation,
  useGetStatsTrendQuery,
  useLazyGetStatsTrendQuery,
  useGetStatsSummaryQuery,
  useLazyGetStatsSummaryQuery,
  useGetCalibrationQuery,
  useLazyGetCalibrationQuery,
  useGetSettingsThresholdsQuery,
  useLazyGetSettingsThresholdsQuery,
  usePutSettingsThresholdsMutation,
  useGetSourcesQuery,
  useLazyGetSourcesQuery,
  usePostSourcesMutation,
  usePatchSourcesByIdMutation,
  usePostScansMutation,
  useGetDocumentsByIdScreenshotAndViewportQuery,
  useLazyGetDocumentsByIdScreenshotAndViewportQuery,
  useGetHealthQuery,
  useLazyGetHealthQuery,
} = injectedRtkApi;

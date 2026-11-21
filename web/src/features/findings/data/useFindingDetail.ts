import { skipToken } from '@reduxjs/toolkit/query';
import { useGetFindingsByIdQuery, type GetFindingsByIdApiResponse } from '../../../api/generated';
import type { FindingDetail } from '../model';

function toDetail(f: GetFindingsByIdApiResponse): FindingDetail {
  return {
    id: f.id,
    module: f.module,
    title: f.title,
    summary: f.summary,
    score: f.score,
    riskLevel: f.risk_level,
    status: f.status,
    note: f.note,
    url: f.url,
    platform: f.platform,
    detectedAt: f.detected_at,
    firm: f.firm
      ? { name: f.firm.name, authorized: f.firm.authorized, registryType: f.firm.registry_type, matchConfidence: f.firm.match_confidence }
      : undefined,
    advertiser: f.advertiser
      ? {
          name: f.advertiser.name,
          handle: f.advertiser.handle,
          profileUrl: f.advertiser.profile_url,
          website: f.advertiser.website,
          inRegistry: f.advertiser.in_registry,
          onWarningList: f.advertiser.on_warning_list,
        }
      : undefined,
    rules: f.rules.map((r) => ({
      ruleId: r.rule_id,
      name: r.name,
      result: r.result,
      severity: r.severity,
      evidence: r.evidence,
      explanation: r.explanation,
      legalBasis: r.legal_basis,
      method: r.method,
    })),
    excerpt: f.content_excerpt,
    documentText: f.document?.text,
    screenshotUrl: f.screenshot_urls?.desktop,
    pipelineVersion: f.model?.pipeline_version,
    llm: f.model?.llm,
  };
}

export type FindingDetailState = { detail: FindingDetail | undefined; isLoading: boolean; isError: boolean; notFound: boolean };

export function useFindingDetail(id: string | undefined): FindingDetailState {
  const { currentData, isFetching, isError, error } = useGetFindingsByIdQuery(id ? { id } : skipToken);
  return {
    detail: currentData ? toDetail(currentData) : undefined,
    isLoading: isFetching && !currentData,
    isError,
    notFound: isError && typeof error === 'object' && error !== null && 'status' in error && error.status === 404,
  };
}

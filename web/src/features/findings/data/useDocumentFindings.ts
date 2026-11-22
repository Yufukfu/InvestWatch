import { skipToken } from '@reduxjs/toolkit/query';
import { useGetFindingsQuery } from '../../../api/generated';
import type { ModuleOption } from '../model';

// At most one finding per (document, module) and three modules exist, so one page of 10 holds them all.
const PAGE_SIZE = 10;

// Every finding of one document, for the detail's module switcher (issue #33). Independent of the
// list filters, so a module filter never hides a sibling. A failure only hides the switcher.
export function useDocumentFindings(documentId: string | undefined): ModuleOption[] {
  const { currentData, isError } = useGetFindingsQuery(documentId ? { documentId, pageSize: PAGE_SIZE } : skipToken);
  if (isError || !currentData) return [];
  // Filter again: a backend that ignores document_id (an older mock server) must not show other posts.
  return currentData.items
    .filter((f) => f.document_id === documentId)
    .map((f) => ({ id: f.id, module: f.module, riskLevel: f.risk_level }))
    .sort((a, b) => a.module.localeCompare(b.module));
}

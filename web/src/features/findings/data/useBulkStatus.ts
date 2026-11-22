import { useCallback, useState } from 'react';
import { usePostFindingsBulkStatusMutation } from '../../../api/generated';
import type { BulkOutcome, BulkTarget, FindingStatus } from '../model';
import { toSaveError, type SaveError } from './useStatusChange';

export type BulkStatusState = {
  /** Sends one request for every target; resolves true on success (the caller then clears its selection). */
  apply: (targets: BulkTarget[], status: FindingStatus) => Promise<boolean>;
  isSaving: boolean;
  outcome: BulkOutcome | undefined;
  error: SaveError | undefined;
  dismiss: () => void;
};

// Not optimistic, like the single PATCH: the list changes only when the API has answered, and the cache
// invalidation (findings, stats, calibration) is set in src/api/enhanced.ts.
export function useBulkStatus(): BulkStatusState {
  const [post, { isLoading }] = usePostFindingsBulkStatusMutation();
  const [outcome, setOutcome] = useState<BulkOutcome>();
  const [error, setError] = useState<SaveError>();

  const apply = useCallback(
    async (targets: BulkTarget[], status: FindingStatus) => {
      setOutcome(undefined);
      setError(undefined);
      const titles = new Map(targets.map((t) => [t.id, t.title]));
      try {
        const res = await post({ body: { ids: targets.map((t) => t.id), status } }).unwrap();
        setOutcome({
          status,
          updated: res.updated,
          notFound: res.not_found,
          items: res.results.map((r) => ({
            id: r.id,
            title: r.finding?.title ?? titles.get(r.id) ?? r.id,
            result: r.result,
          })),
        });
        return true;
      } catch (e) {
        setError(toSaveError(e));
        return false;
      }
    },
    [post],
  );
  const dismiss = useCallback(() => setOutcome(undefined), []);
  return { apply, isSaving: isLoading, outcome, error, dismiss };
}

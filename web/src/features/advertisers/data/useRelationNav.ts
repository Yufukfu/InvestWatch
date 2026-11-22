import { useCallback, useMemo } from 'react';
import { FINDINGS_SECTION, goToSection } from '../../../url/section';
import { useUrlSearch } from '../../../url/useUrlSearch';
import type { Relation, RelationNav } from '../model';
import { findingSearch, parseRelation, relationSearch } from './relationUrl';

export const ADVERTISERS_SECTION = 'powiazania';

// The relation page's URL state: which relation is open, and the moves between the graph, a relation and a
// finding. Each move pushes a history entry, so the browser back button retraces it.
export function useRelationNav(): RelationNav & {
  relation: Relation | undefined;
  closeRelation: () => void;
  openFinding: (id: string) => void;
} {
  const [search, push] = useUrlSearch();
  const relation = useMemo(() => parseRelation(search), [search]);
  const relationHref = useCallback(
    (r: Relation) => `${window.location.pathname}${relationSearch(search, r)}#${ADVERTISERS_SECTION}`,
    [search],
  );
  const onOpenRelation = useCallback((r: Relation) => push(relationSearch(window.location.search, r)), [push]);
  const closeRelation = useCallback(() => push(relationSearch(window.location.search, undefined)), [push]);
  const openFinding = useCallback(
    (id: string) => {
      push(findingSearch(window.location.search, id));
      goToSection(FINDINGS_SECTION);
    },
    [push],
  );
  return { relation, relationHref, onOpenRelation, closeRelation, openFinding };
}

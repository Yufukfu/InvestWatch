// The dashboard's pages are addressed by the URL hash (see App). An action in one page that shows a
// finding (triage, the toast) switches to the findings page with this; the search string is set first.
export const FINDINGS_SECTION = 'zgloszenia';

export function goToSection(id: string): void {
  if (window.location.hash !== `#${id}`) window.location.hash = id;
}

// Parameters of the findings page (the names of GET /findings, plus the one-shot `triage` and the open `finding`).
const FINDINGS_PARAMS = ['finding', 'triage', 'module', 'status', 'risk_level', 'platform', 'score_min', 'date_from', 'date_to', 'q', 'sort', 'page', 'page_size'];

// A link made before the pages were split, or typed by hand, has these without a hash.
export function hasFindingsParams(search: string): boolean {
  const p = new URLSearchParams(search);
  return FINDINGS_PARAMS.some((name) => p.has(name));
}

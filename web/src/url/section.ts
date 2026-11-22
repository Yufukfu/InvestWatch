// The dashboard's pages are addressed by the URL hash (see App). An action in one page that shows a
// finding (triage, the toast) switches to the findings page with this; the search string is set first.
export const FINDINGS_SECTION = 'zgloszenia';

export function goToSection(id: string): void {
  if (window.location.hash !== `#${id}`) window.location.hash = id;
}

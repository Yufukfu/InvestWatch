import { lazy, Suspense, useEffect, useId, useRef, useState, type ReactNode } from 'react';
import { SectionBoundary } from './SectionBoundary';
import { AlertsPage } from './features/alerts/AlertsPage';
import { HealthPage } from './features/health/HealthPage';
import { FindingsPage } from './features/findings/FindingsPage';
import { SummaryPage } from './features/summary/SummaryPage';
import { ToastSlotProvider } from './ToastSlotProvider';
import { FINDINGS_SECTION, hasFindingsParams } from './url/section';

// Recharts is the largest dependency; the chart sections load as their own chunks and share it.
const TrendPage = lazy(() => import('./features/trend/TrendPage').then((m) => ({ default: m.TrendPage })));
const CalibrationPage = lazy(() =>
  import('./features/calibration/CalibrationPage').then((m) => ({ default: m.CalibrationPage })),
);

// Sub-pages: the hash picks the one page that is rendered; the header stays on every page.
const SECTION_LINKS = [
  { id: 'przeglad', label: 'Przegląd' },
  { id: 'zgloszenia', label: 'Zgłoszenia' },
  { id: 'kalibracja', label: 'Kalibracja' },
];

// The page the hash names. With no valid hash, a link that addresses findings (`?finding=`, a filter) opens the
// findings page and the hash is written in place (no history entry); anything else shows the overview.
function currentHash(): string {
  const hash = window.location.hash.slice(1);
  if (SECTION_LINKS.some((l) => l.id === hash) || !hasFindingsParams(window.location.search)) return hash;
  window.history.replaceState(null, '', `${window.location.pathname}${window.location.search}#${FINDINGS_SECTION}`);
  return FINDINGS_SECTION;
}

function useActiveSection(): string {
  const [hash, setHash] = useState(currentHash);
  useEffect(() => {
    const onChange = () => setHash(currentHash());
    window.addEventListener('hashchange', onChange);
    return () => window.removeEventListener('hashchange', onChange);
  }, []);
  return SECTION_LINKS.some((l) => l.id === hash) ? hash : SECTION_LINKS[0].id;
}

const PAGES: Record<string, ReactNode> = {
  przeglad: (
    <div className="stack">
      <SummaryPage />
      <SectionBoundary
        fallback={
          <p className="trend-state" role="alert">
            Nie udało się pobrać danych trendu.
          </p>
        }
      >
        <Suspense fallback={<p className="trend-state" role="status">Ładowanie wykresu…</p>}>
          <TrendPage />
        </Suspense>
      </SectionBoundary>
    </div>
  ),
  zgloszenia: <FindingsPage />,
  kalibracja: (
    <SectionBoundary
      fallback={
        <p className="trend-state" role="alert">
          Nie udało się wczytać panelu kalibracji.
        </p>
      }
    >
      <Suspense fallback={<p className="trend-state" role="status">Ładowanie kalibracji…</p>}>
        <CalibrationPage />
      </Suspense>
    </SectionBoundary>
  ),
};

export function App() {
  const active = useActiveSection();
  const navId = useId();
  // Only meaningful below 600px, where the CSS hides the section links until the menu button opens them.
  const [menuOpen, setMenuOpen] = useState(false);
  // Where the connection-lost banner is drawn: above the page content, outside the header row.
  const [bannerNode, setBannerNode] = useState<HTMLElement | null>(null);
  // A page change starts at the top with focus on the page, not on the link that was followed; the first render does not move focus.
  const mainRef = useRef<HTMLElement>(null);
  const shown = useRef(active);
  useEffect(() => {
    if (shown.current === active) return;
    shown.current = active;
    window.scrollTo(0, 0);
    mainRef.current?.focus({ preventScroll: true });
  }, [active]);
  const page = PAGES[active];
  return (
    <ToastSlotProvider>
      <header className="app-header">
        <div className="app-header-inner">
          <div className="brand">
            <h1>InvestWatch</h1>
            <span className="brand-tagline">NARZĘDZIE NADZORCZE</span>
          </div>
          <nav id={navId} className={menuOpen ? 'app-nav app-nav-open' : 'app-nav'} aria-label="Sekcje">
            {SECTION_LINKS.map((l) => (
              <a key={l.id} href={`#${l.id}`} onClick={() => setMenuOpen(false)} aria-current={l.id === active ? 'location' : undefined}>
                {l.label}
              </a>
            ))}
          </nav>
          <div className="header-status">
            <AlertsPage bannerNode={bannerNode} />
            <HealthPage />
          </div>
          <button
            type="button"
            className="nav-toggle"
            aria-label="Menu"
            aria-expanded={menuOpen}
            aria-controls={navId}
            onClick={() => setMenuOpen((o) => !o)}
          >
            <span aria-hidden="true">☰</span>
          </button>
        </div>
      </header>
      <div className="app">
        <div ref={setBannerNode} className="banner-slot" />
        <main ref={mainRef} tabIndex={-1}>
          {page}
        </main>
      </div>
    </ToastSlotProvider>
  );
}

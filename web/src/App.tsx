import { lazy, Suspense, useEffect, useId, useState } from 'react';
import { SectionBoundary } from './SectionBoundary';
import { AlertsPage } from './features/alerts/AlertsPage';
import { HealthPage } from './features/health/HealthPage';
import { FindingsPage } from './features/findings/FindingsPage';
import { SummaryPage } from './features/summary/SummaryPage';
import { ToastSlotProvider } from './ToastSlotProvider';

// Recharts is the largest dependency; the chart sections load as their own chunks and share it.
const TrendPage = lazy(() => import('./features/trend/TrendPage').then((m) => ({ default: m.TrendPage })));
const CalibrationPage = lazy(() =>
  import('./features/calibration/CalibrationPage').then((m) => ({ default: m.CalibrationPage })),
);

// In-page anchors: the targets are wrappers rendered at once, so a link works before the data or a lazy chunk arrives.
const SECTION_LINKS = [
  { id: 'przeglad', label: 'Przegląd' },
  { id: 'zgloszenia', label: 'Zgłoszenia' },
  { id: 'kalibracja', label: 'Kalibracja' },
];

// The first section is current until a link changes the hash; the sections are anchors, so the hash is the state.
function useActiveSection(): string {
  const [hash, setHash] = useState(() => window.location.hash.slice(1));
  useEffect(() => {
    const onChange = () => setHash(window.location.hash.slice(1));
    window.addEventListener('hashchange', onChange);
    return () => window.removeEventListener('hashchange', onChange);
  }, []);
  return SECTION_LINKS.some((l) => l.id === hash) ? hash : SECTION_LINKS[0].id;
}

export function App() {
  const active = useActiveSection();
  const navId = useId();
  // Only meaningful below 600px, where the CSS hides the section links until the menu button opens them.
  const [menuOpen, setMenuOpen] = useState(false);
  // Where the connection-lost banner is drawn: above the page content, outside the header row.
  const [bannerNode, setBannerNode] = useState<HTMLElement | null>(null);
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
        <main>
          <div id="przeglad" className="stack">
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
          <div id="zgloszenia">
            <FindingsPage />
          </div>
          <div id="kalibracja">
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
          </div>
        </main>
      </div>
    </ToastSlotProvider>
  );
}

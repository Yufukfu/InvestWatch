import { lazy, Suspense } from 'react';
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

export function App() {
  return (
    <ToastSlotProvider>
      <header className="app-header">
        <div className="app-header-inner">
          <div className="brand">
            <span className="brand-eyebrow">NARZĘDZIE NADZORCZE</span>
            <h1>InvestWatch</h1>
            <span className="brand-sub">Monitoring ryzykownych treści inwestycyjnych</span>
          </div>
          <nav className="app-nav" aria-label="Sekcje">
            {SECTION_LINKS.map((l) => (
              <a key={l.id} href={`#${l.id}`}>
                {l.label}
              </a>
            ))}
          </nav>
          <div className="header-status">
            <AlertsPage />
            <HealthPage />
          </div>
        </div>
      </header>
      <div className="app">
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

import { lazy, Suspense } from 'react';
import { SectionBoundary } from './SectionBoundary';
import { AlertsPage } from './features/alerts/AlertsPage';
import { HealthPage } from './features/health/HealthPage';
import { FindingsPage } from './features/findings/FindingsPage';
import { SummaryPage } from './features/summary/SummaryPage';

// Recharts is the largest dependency; the chart sections load as their own chunks and share it.
const TrendPage = lazy(() => import('./features/trend/TrendPage').then((m) => ({ default: m.TrendPage })));
const CalibrationPage = lazy(() =>
  import('./features/calibration/CalibrationPage').then((m) => ({ default: m.CalibrationPage })),
);

export function App() {
  return (
    <>
      <header className="app-header">
        <div className="app-header-inner">
          <div className="brand">
            <h1>InvestWatch</h1>
            <span className="brand-sub">Monitoring ryzykownych treści inwestycyjnych</span>
          </div>
          <div className="header-status">
            <AlertsPage />
            <HealthPage />
          </div>
        </div>
      </header>
      <div className="app">
        <main>
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
          <FindingsPage />
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
        </main>
      </div>
    </>
  );
}

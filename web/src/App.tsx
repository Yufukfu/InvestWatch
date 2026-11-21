import { lazy, Suspense } from 'react';
import { HealthPage } from './features/health/HealthPage';
import { FindingsPage } from './features/findings/FindingsPage';
import { SummaryPage } from './features/summary/SummaryPage';

// Recharts is the largest dependency; load the trend section as its own chunk.
const TrendPage = lazy(() => import('./features/trend/TrendPage').then((m) => ({ default: m.TrendPage })));

export function App() {
  return (
    <div className="app">
      <header className="app-header">
        <h1>InvestWatch</h1>
        <HealthPage />
      </header>
      <main>
        <SummaryPage />
        <Suspense fallback={<p className="trend-state" role="status">Ładowanie wykresu…</p>}>
          <TrendPage />
        </Suspense>
        <FindingsPage />
      </main>
    </div>
  );
}

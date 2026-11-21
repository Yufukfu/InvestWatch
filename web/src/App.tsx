import { HealthPage } from './features/health/HealthPage';
import { FindingsPage } from './features/findings/FindingsPage';
import { SummaryPage } from './features/summary/SummaryPage';
import { TrendPage } from './features/trend/TrendPage';

export function App() {
  return (
    <div className="app">
      <header className="app-header">
        <h1>InvestWatch</h1>
        <HealthPage />
      </header>
      <main>
        <SummaryPage />
        <TrendPage />
        <FindingsPage />
      </main>
    </div>
  );
}

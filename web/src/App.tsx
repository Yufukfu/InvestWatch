import { HealthPage } from './features/health/HealthPage';
import { FindingsPage } from './features/findings/FindingsPage';
import { SummaryPage } from './features/summary/SummaryPage';

export function App() {
  return (
    <div className="app">
      <header className="app-header">
        <h1>InvestWatch</h1>
        <HealthPage />
      </header>
      <main>
        <SummaryPage />
        <FindingsPage />
      </main>
    </div>
  );
}

import { HealthPage } from './features/health/HealthPage';
import { FindingsTable } from './features/findings/FindingsTable';
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
        <FindingsTable />
      </main>
    </div>
  );
}

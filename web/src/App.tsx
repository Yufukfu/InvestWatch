import { HealthPage } from './features/health/HealthPage';
import { FindingsTable } from './features/findings/FindingsTable';
import { SummaryCards } from './features/findings/SummaryCards';

export function App() {
  return (
    <div className="app">
      <header className="app-header">
        <h1>InvestWatch</h1>
        <HealthPage />
      </header>
      <main>
        <SummaryCards />
        <FindingsTable />
      </main>
    </div>
  );
}

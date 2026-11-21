import { HealthBadge } from './features/health/HealthBadge';
import { FindingsTable } from './features/findings/FindingsTable';
import { SummaryCards } from './features/findings/SummaryCards';
import { TrendPage } from './features/trend/TrendPage';

export function App() {
  return (
    <div className="app">
      <header className="app-header">
        <h1>InvestWatch</h1>
        <HealthBadge />
      </header>
      <main>
        <SummaryCards />
        <TrendPage />
        <FindingsTable />
      </main>
    </div>
  );
}

import { AdvertisersTable } from './components/AdvertisersTable';
import { useAdvertisers } from './data/useAdvertisers';

// Who promotes which licensed firm (M1, issue #72): advertisers of M1 findings with their firms.
export function AdvertisersPage() {
  const view = useAdvertisers();
  return (
    <section className="panel" aria-labelledby="advertisers-heading">
      <div className="panel-header">
        <h2 id="advertisers-heading">Reklamodawcy i promowane firmy (M1)</h2>
      </div>
      <AdvertisersTable {...view} />
    </section>
  );
}

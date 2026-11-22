import type { M2CoverageCounts } from '../model';

type Props = { coverage: M2CoverageCounts | undefined };

// Share of M2 findings whose firm matched a KNF register entry (GET /stats/summary m2_coverage).
// The text carries the value; the bar repeats it as length and is hidden from assistive technology.
export function M2Coverage({ coverage }: Props) {
  let text: string;
  let percent: number | undefined;
  if (!coverage) text = 'brak danych';
  else if (coverage.total === 0) text = 'Brak zgłoszeń M2.';
  else {
    percent = Math.round(Math.min(1, Math.max(0, coverage.registryMatched / coverage.total)) * 100);
    const noun = coverage.total === 1 ? 'zgłoszenia' : 'zgłoszeń';
    text = `${coverage.registryMatched} z ${coverage.total} ${noun} M2 dopasowano do rejestru KNF (${percent}%)`;
  }
  return (
    <section className="coverage" aria-labelledby="m2-coverage-heading">
      <h3 id="m2-coverage-heading" className="coverage-eyebrow">
        Pokrycie rejestrem KNF · M2
      </h3>
      <p className="coverage-text">{text}</p>
      <div className="coverage-bar" aria-hidden="true">
        {percent !== undefined && <span style={{ width: `${percent}%` }} />}
      </div>
    </section>
  );
}

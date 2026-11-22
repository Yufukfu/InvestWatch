import type { AdvertiserKpis } from '../filters';
import { plural } from './labels';

// The KPI sentence of the Powiązania page: "<N> reklamodawców promuje <M> licencjonowanych firm, w tym <R> powtarzających się".
export function AdvertisersHero({ kpis }: { kpis: AdvertiserKpis }) {
  return (
    <section className="hero adv-hero" aria-labelledby="adv-hero-eyebrow">
      <h2 id="adv-hero-eyebrow" className="hero-eyebrow">
        POWIĄZANIA · M1 · FINFLUENCERZY I FIRMY Z REJESTRU
      </h2>
      <p className="hero-figures adv-figures">
        <span className="hero-value" data-kpi="advertisers">{kpis.advertisers}</span>{' '}
        <span className="hero-label">{plural(kpis.advertisers, 'reklamodawca promuje', 'reklamodawcy promują', 'reklamodawców promuje')}</span>{' '}
        <span className="hero-value" data-kpi="firms">{kpis.firms}</span>{' '}
        <span className="hero-label">
          {plural(kpis.firms, 'licencjonowaną firmę', 'licencjonowane firmy', 'licencjonowanych firm')}, w tym
        </span>{' '}
        <span className="hero-value hero-value-risk" data-kpi="repeat">{kpis.repeat}</span>{' '}
        <span className="hero-label">{kpis.repeat === 1 ? 'powtarzający się' : 'powtarzających się'}</span>
      </p>
    </section>
  );
}

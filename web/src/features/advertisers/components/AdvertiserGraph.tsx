import { isolate } from '../../../format/bidi';
import { EDGE_AREA_WIDTH as W, type Graph, type GraphEdge } from '../graph';
import type { Relation } from '../model';
import { plural } from './labels';

type Props = {
  graph: Graph;
  // The advertiser picked in the side table: its edges are drawn on top and the other red edges fade.
  selected: string | undefined;
  onOpenRelation: (relation: Relation) => void;
};

// Horizontal cubic curve from the advertiser column (x = 0) to the firm column (x = W), drawn 1:1 in pixels.
function edgePath(e: GraphEdge): string {
  return `M0 ${e.y1} C${W / 2} ${e.y1}, ${W / 2} ${e.y2}, ${W} ${e.y2}`;
}

function edgeClass(e: GraphEdge, selected: string | undefined): string {
  const base = e.repeat ? 'adv-edge adv-edge-repeat' : 'adv-edge adv-edge-single';
  if (!selected) return base;
  if (e.advertiser === selected) return `${base} adv-edge-selected`;
  return `${base} adv-edge-dim`;
}

// Advertiser handles and firm names are untrusted: HTML labels next to the SVG, each in its own dir="auto"
// element; the SVG only draws the edges. The same data is in the "Tabela" view (keyboard and screen readers).
export function AdvertiserGraph({ graph, selected: picked, onOpenRelation }: Props) {
  // An advertiser with no matched firm has no edges: nothing to highlight, so nothing fades.
  const selected = graph.advertisers.some((a) => a.key === picked) ? picked : undefined;
  const labels = new Map(graph.advertisers.map((a) => [a.key, a.label]));
  const firms = new Map(graph.firms.map((f) => [f.key, f.name]));
  // The selected advertiser's edges are drawn last, so they are on top.
  const edges = [...graph.edges].sort((a, b) => Number(a.advertiser === selected) - Number(b.advertiser === selected));
  const summary = `Graf powiązań: ${graph.advertisers.length} ${plural(graph.advertisers.length, 'reklamodawca', 'reklamodawców', 'reklamodawców')}, ${graph.firms.length} ${plural(graph.firms.length, 'firma', 'firmy', 'firm')}, ${graph.edges.length} ${plural(graph.edges.length, 'relacja', 'relacje', 'relacji')}. Te same dane są w widoku Tabela.`;
  return (
    <figure className="adv-graph">
      <p className="adv-graph-hint">Przewiń graf w bok, aby zobaczyć firmy.</p>
      <div className="adv-graph-scroll">
        <div className="adv-graph-inner">
          <div className="adv-graph-heads" aria-hidden="true">
            <span>Reklamodawcy</span>
            <span />
            <span>Firmy z rejestru</span>
          </div>
          <div className="adv-graph-body" style={{ height: graph.height }}>
            <ul className="adv-graph-col adv-graph-left" aria-label="Reklamodawcy">
              {graph.advertisers.map((a) => (
                <li
                  key={a.key}
                  style={{ top: a.y }}
                  className={[a.repeat && 'repeat', a.key === selected && 'selected'].filter(Boolean).join(' ') || undefined}
                >
                  <span className="adv-graph-name" dir="auto">
                    {a.label}
                  </span>
                  <span className="adv-graph-count">{a.count}</span>
                  <span className="adv-graph-dot" aria-hidden="true" />
                </li>
              ))}
            </ul>
            <svg className="adv-graph-edges" role="img" aria-label={summary} width={W} height={graph.height} viewBox={`0 0 ${W} ${graph.height}`}>
              {edges.map((e) => (
                <g
                  key={`${e.advertiser}|${e.firm}`}
                  data-edge={`${e.advertiser}|${e.firm}`}
                  className={edgeClass(e, selected)}
                  onClick={() => onOpenRelation({ advertiser: e.advertiser, firm: e.firm })}
                >
                  <title>{`${isolate(labels.get(e.advertiser) ?? '')} → ${isolate(firms.get(e.firm) ?? '')}: ${e.count}`}</title>
                  <path className="adv-edge-line" d={edgePath(e)} strokeWidth={e.width} />
                  <path className="adv-edge-hit" d={edgePath(e)} strokeWidth={14} />
                </g>
              ))}
            </svg>
            <ul className="adv-graph-col adv-graph-right" aria-label="Firmy z rejestru">
              {graph.firms.map((f) => (
                <li key={f.key} style={{ top: f.y }}>
                  <span className="adv-graph-dot" aria-hidden="true" />
                  <span className="adv-graph-count">{f.count}</span>
                  <span className="adv-graph-name" dir="auto">
                    {f.name}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        </div>
      </div>
      <figcaption className="adv-legend">
        <span className="adv-legend-item">
          <span className="adv-legend-line adv-legend-repeat" aria-hidden="true" />
          Powtarzający się: 2+ firmy lub 5+ zgłoszeń
        </span>
        <span className="adv-legend-item">
          <span className="adv-legend-line adv-legend-single" aria-hidden="true" />
          Pojedyncza relacja
        </span>
        <span className="adv-legend-item muted">Grubość linii = liczba zgłoszeń reklam</span>
        {(graph.hidden > 0 || graph.unmatched > 0) && (
          <span className="adv-legend-item muted">
            {[
              graph.hidden > 0 && `Pominięto ${graph.hidden} rzadszych reklamodawców`,
              graph.unmatched > 0 && `${graph.unmatched} bez dopasowanej firmy`,
            ]
              .filter(Boolean)
              .join(' · ')}{' '}
            – pełna lista w widoku Tabela.
          </span>
        )}
      </figcaption>
    </figure>
  );
}

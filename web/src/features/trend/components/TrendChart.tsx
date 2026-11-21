import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';

export type TrendBucket = 'hour' | 'day';

// App-owned shape: a count may be absent and is then drawn as 0.
export type TrendPoint = { t: string; M1?: number; M2?: number; M3?: number };

export type TrendChartProps = {
  points: TrendPoint[];
  bucket: TrendBucket;
  onBucketChange: (bucket: TrendBucket) => void;
  isLoading: boolean;
  isError: boolean;
  /** Fixed size for tests: jsdom has no ResizeObserver, so ResponsiveContainer cannot measure. */
  size?: { width: number; height: number };
};

// Series differ by colour and by dash pattern, and the legend names them: never colour alone.
const SERIES = [
  { key: 'M1', color: '#1d4ed8', dash: undefined },
  { key: 'M2', color: '#b45309', dash: '6 3' },
  { key: 'M3', color: '#047857', dash: '2 3' },
] as const;

const BUCKETS: { value: TrendBucket; label: string }[] = [
  { value: 'hour', label: 'Godzina' },
  { value: 'day', label: 'Dzień' },
];

function formatTick(t: string, bucket: TrendBucket) {
  const date = new Date(t);
  return bucket === 'hour'
    ? date.toLocaleTimeString('pl-PL', { hour: '2-digit', minute: '2-digit' })
    : date.toLocaleDateString('pl-PL', { day: 'numeric', month: 'short' });
}

export function TrendChart({ points, bucket, onBucketChange, isLoading, isError, size }: TrendChartProps) {
  const data = points.map((p) => ({ t: p.t, M1: p.M1 ?? 0, M2: p.M2 ?? 0, M3: p.M3 ?? 0 }));
  const totals = SERIES.map((s) => ({ ...s, total: data.reduce((sum, p) => sum + p[s.key], 0) }));
  const hasData = totals.some((s) => s.total > 0);

  const chart = (width?: number, height?: number) => (
    <LineChart width={width} height={height} data={data} margin={{ top: 8, right: 16, bottom: 4, left: 0 }}>
      <CartesianGrid stroke="#e5e7eb" vertical={false} />
      <XAxis dataKey="t" tickFormatter={(t: string) => formatTick(t, bucket)} minTickGap={24} />
      <YAxis allowDecimals={false} width={32} />
      <Tooltip labelFormatter={(t) => formatTick(String(t), bucket)} />
      {SERIES.map((s) => (
        <Line
          key={s.key}
          dataKey={s.key}
          stroke={s.color}
          strokeDasharray={s.dash}
          strokeWidth={2}
          dot={false}
          isAnimationActive={false}
        />
      ))}
    </LineChart>
  );

  let body;
  if (isLoading) {
    body = <p className="trend-state">Ładowanie wykresu…</p>;
  } else if (isError) {
    body = (
      <p className="trend-state" role="alert">
        Nie udało się pobrać danych trendu.
      </p>
    );
  } else if (!hasData) {
    body = <p className="trend-state">Brak danych w wybranym okresie.</p>;
  } else {
    body = (
      <>
        <div
          role="img"
          className="trend-plot"
          aria-label={`Liczba zgłoszeń: ${totals.map((s) => `${s.key} ${s.total}`).join(', ')}`}
        >
          {size ? (
            chart(size.width, size.height)
          ) : (
            <ResponsiveContainer width="100%" height={260}>
              {chart()}
            </ResponsiveContainer>
          )}
        </div>
        <ul className="trend-legend" aria-label="Legenda">
          {totals.map((s) => (
            <li key={s.key}>
              <svg width="28" height="10" aria-hidden="true">
                <line x1="0" y1="5" x2="28" y2="5" stroke={s.color} strokeWidth="2" strokeDasharray={s.dash} />
              </svg>
              {s.key}
            </li>
          ))}
        </ul>
      </>
    );
  }

  return (
    <section className="trend" aria-label="Trend zgłoszeń">
      <div className="trend-header">
        <h2>Trend zgłoszeń</h2>
        <div className="trend-buckets">
          {BUCKETS.map((b) => (
            <button key={b.value} type="button" aria-pressed={bucket === b.value} onClick={() => onBucketChange(b.value)}>
              {b.label}
            </button>
          ))}
        </div>
      </div>
      {body}
    </section>
  );
}

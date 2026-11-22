import { CartesianGrid, Line, LineChart, ReferenceDot, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { formatPercent, formatThreshold } from '../format';
import { markerSides, type CalibrationPoint } from '../model';

type Props = {
  points: CalibrationPoint[];
  current: number;
  selected: number;
  /** Fixed size for tests: jsdom has no ResizeObserver (ADR 0203). */
  size?: { width: number; height: number };
};

const TICK = { fontFamily: 'var(--font-mono)', fontSize: 12, fill: 'var(--muted)' };

// Precision (ink, solid) and recall (blue, dashed) differ by colour and dash pattern; the panel's table is the
// text alternative. The two markers carry their threshold in their label.
export function CalibrationChart({ points, current, selected, size }: Props) {
  const sides = markerSides(current, selected);
  const at = points.find((p) => p.threshold === selected);
  const chart = (width?: number, height?: number) => (
    <LineChart width={width} height={height} data={points} accessibilityLayer={false} margin={{ top: 16, right: 16, bottom: 4, left: 0 }}>
      <CartesianGrid stroke="var(--border)" vertical={false} />
      <XAxis dataKey="threshold" type="number" domain={[0, 1]} ticks={[0, 0.2, 0.4, 0.6, 0.8, 1]} tickFormatter={formatThreshold} tick={TICK} tickLine={false} axisLine={{ stroke: 'var(--accent)' }} tickMargin={8} />
      <YAxis domain={[0, 1]} tickFormatter={formatPercent} width={52} tick={TICK} tickLine={false} axisLine={false} />
      <Tooltip formatter={(v) => formatPercent(Number(v))} labelFormatter={(v) => `próg ${formatThreshold(Number(v))}`} />
      <ReferenceLine
        x={current}
        stroke="var(--muted)"
        strokeDasharray="3 4"
        label={{ value: `obecny ${formatThreshold(current)}`, position: sides.current, fill: 'var(--muted)', fontSize: 12, fontFamily: 'var(--font-mono)' }}
      />
      {selected !== current && (
        <ReferenceLine
          x={selected}
          stroke="var(--link)"
          strokeWidth={2}
          label={{ value: `wybrany ${formatThreshold(selected)}`, position: sides.selected, fill: 'var(--link)', fontSize: 12, fontWeight: 600, fontFamily: 'var(--font-mono)' }}
        />
      )}
      <Line type="monotone" dataKey="precision" name="Precyzja" stroke="var(--accent)" strokeWidth={2.5} dot={false} isAnimationActive={false} />
      <Line type="monotone" dataKey="recall" name="Czułość" stroke="var(--link)" strokeDasharray="7 5" strokeWidth={2.5} dot={false} isAnimationActive={false} />
      {at && <ReferenceDot x={selected} y={at.precision} r={5} fill="var(--accent)" stroke="none" ifOverflow="visible" />}
      {at && <ReferenceDot x={selected} y={at.recall} r={5} fill="var(--link)" stroke="none" ifOverflow="visible" />}
    </LineChart>
  );
  return (
    <div
      className="calibration-plot"
      role="img"
      aria-label={`Precyzja i czułość w zależności od progu; obecny ${formatThreshold(current)}, wybrany ${formatThreshold(selected)}`}
    >
      {size ? chart(size.width, size.height) : <ResponsiveContainer width="100%" height={280}>{chart()}</ResponsiveContainer>}
      <ul className="trend-legend" aria-hidden="true">
        <li>
          <svg width="24" height="10"><line x1="0" y1="5" x2="24" y2="5" stroke="var(--accent)" strokeWidth="3" strokeLinecap="round" /></svg>Precyzja — mało fałszywych alarmów
        </li>
        <li>
          <svg width="24" height="10"><line x1="0" y1="5" x2="24" y2="5" stroke="var(--link)" strokeWidth="3" strokeDasharray="7 5" strokeLinecap="round" /></svg>Czułość — mało przeoczonych naruszeń
        </li>
      </ul>
    </div>
  );
}

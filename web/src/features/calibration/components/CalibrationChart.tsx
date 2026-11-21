import { CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { formatPercent, formatThreshold } from '../format';
import { markerSides, type CalibrationPoint } from '../model';

type Props = {
  points: CalibrationPoint[];
  current: number;
  selected: number;
  /** Fixed size for tests: jsdom has no ResizeObserver (ADR 0203). */
  size?: { width: number; height: number };
};

// Precision and recall differ by colour and dash pattern; the panel's table is the text alternative.
export function CalibrationChart({ points, current, selected, size }: Props) {
  const sides = markerSides(current, selected);
  const chart = (width?: number, height?: number) => (
    <LineChart width={width} height={height} data={points} accessibilityLayer={false} margin={{ top: 16, right: 16, bottom: 4, left: 0 }}>
      <CartesianGrid stroke="#e5e7eb" vertical={false} />
      <XAxis dataKey="threshold" type="number" domain={[0, 1]} ticks={[0, 0.2, 0.4, 0.6, 0.8, 1]} tickFormatter={formatThreshold} />
      <YAxis domain={[0, 1]} tickFormatter={formatPercent} width={52} />
      <Tooltip formatter={(v) => formatPercent(Number(v))} labelFormatter={(v) => `próg ${formatThreshold(Number(v))}`} />
      <ReferenceLine x={current} stroke="#6b7280" strokeDasharray="4 3" label={{ value: 'obecny', position: sides.current, fill: '#374151', fontSize: 13 }} />
      {selected !== current && (
        <ReferenceLine x={selected} stroke="#1d4ed8" strokeWidth={2} label={{ value: 'wybrany', position: sides.selected, fill: '#1d4ed8', fontSize: 13 }} />
      )}
      <Line type="monotone" dataKey="precision" name="Precyzja" stroke="#b45309" strokeWidth={2} dot={false} isAnimationActive={false} />
      <Line type="monotone" dataKey="recall" name="Czułość" stroke="#047857" strokeDasharray="6 3" strokeWidth={2} dot={false} isAnimationActive={false} />
    </LineChart>
  );
  return (
    <div
      className="calibration-plot"
      role="img"
      aria-label={`Precyzja i czułość w zależności od progu; obecny ${formatThreshold(current)}, wybrany ${formatThreshold(selected)}`}
    >
      {size ? chart(size.width, size.height) : <ResponsiveContainer width="100%" height={240}>{chart()}</ResponsiveContainer>}
      <ul className="trend-legend" aria-hidden="true">
        <li>
          <svg width="28" height="10"><line x1="0" y1="5" x2="28" y2="5" stroke="#b45309" strokeWidth="2" /></svg>Precyzja
        </li>
        <li>
          <svg width="28" height="10"><line x1="0" y1="5" x2="28" y2="5" stroke="#047857" strokeWidth="2" strokeDasharray="6 3" /></svg>Czułość
        </li>
      </ul>
    </div>
  );
}

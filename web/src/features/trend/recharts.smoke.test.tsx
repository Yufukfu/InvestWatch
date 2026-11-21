import { render } from '@testing-library/react';
import { Line, LineChart, XAxis } from 'recharts';
import { expect, it } from 'vitest';

// ADR 0203: charts get a fixed width/height in tests because jsdom has no ResizeObserver.
it('renders a Recharts line chart in jsdom with a fixed size', () => {
  const { container } = render(
    <LineChart width={400} height={200} data={[{ t: 'a', M1: 1 }, { t: 'b', M1: 3 }]}>
      <XAxis dataKey="t" />
      <Line dataKey="M1" isAnimationActive={false} />
    </LineChart>,
  );
  expect(container.querySelector('svg.recharts-surface')).not.toBeNull();
  expect(container.querySelector('path.recharts-line-curve')).not.toBeNull();
});

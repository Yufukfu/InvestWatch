import { render, screen } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { describe, expect, it } from 'vitest';
import summary from '../../mocks/fixtures/summary.json';
import { server } from '../../test/setup';
import { storeWrapper } from '../../test/store';
import { SummaryPage } from './SummaryPage';

describe('SummaryPage', () => {
  it('renders the counts from the API', async () => {
    render(<SummaryPage />, { wrapper: storeWrapper() });
    const region = await screen.findByRole('region', { name: 'Podsumowanie' });
    expect(region).toHaveTextContent(`${summary.total}Wszystkie zgłoszenia`);
    expect(region).toHaveTextContent(`${summary.by_risk_level.high}Wysokie ryzyko`);
    expect(region).toHaveTextContent(`${summary.by_status.new}Nowe`);
  });

  it('renders nothing when the request fails', async () => {
    let hit = false;
    server.use(
      http.get('http://localhost/api/stats/summary', () => {
        hit = true;
        return HttpResponse.error();
      }),
    );
    const { container } = render(<SummaryPage />, { wrapper: storeWrapper() });
    await expect.poll(() => hit).toBe(true);
    expect(container).toBeEmptyDOMElement();
  });
});

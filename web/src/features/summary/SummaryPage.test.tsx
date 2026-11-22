import { render, screen } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { Provider } from 'react-redux';
import { describe, expect, it } from 'vitest';
import { investWatchApi } from '../../api/generated';
import summary from '../../test/fixtures/summary.json';
import { server } from '../../test/setup';
import { makeStore, storeWrapper } from '../../test/store';
import { SummaryPage } from './SummaryPage';

describe('SummaryPage', () => {
  it('renders the counts from the API', async () => {
    render(<SummaryPage />, { wrapper: storeWrapper() });
    const region = await screen.findByRole('region', { name: 'Podsumowanie' });
    expect(region).toHaveTextContent(`${summary.total} zgłoszeń, z czego ${summary.by_risk_level.high} wysokiego ryzyka`);
    expect(region).toHaveTextContent(/PRZEGLĄD · \d{2}\.\d{2}\.\d{4}/);
    expect(region).toHaveTextContent(`${summary.by_status.new}Nowe, bez decyzji`);
    expect(region).toHaveTextContent(`${summary.by_module.M1}M1 · Finfluencerzy`);
  });

  it('renders nothing once the request has failed', async () => {
    server.use(http.get('http://localhost/api/stats/summary', () => HttpResponse.error()));
    const store = makeStore();
    const { container } = render(
      <Provider store={store}>
        <SummaryPage />
      </Provider>,
    );
    // Wait for the settled failure, not just for the request to be sent.
    await expect.poll(() => investWatchApi.endpoints.getStatsSummary.select()(store.getState()).isError).toBe(true);
    expect(container).toBeEmptyDOMElement();
  });
});

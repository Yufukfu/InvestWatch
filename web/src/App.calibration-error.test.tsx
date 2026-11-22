import { render, screen } from '@testing-library/react';
import { Provider } from 'react-redux';
import { describe, expect, it, vi } from 'vitest';
import { App } from './App';
import summary from './test/fixtures/summary.json';
import { makeStore } from './test/store';

vi.mock('socket.io-client', async () => (await import('./test/inertSocket')).inertSocketModule);

// The calibration chunk cannot load (stale tab after a redeploy): reading the export rejects the import.
vi.mock('./features/calibration/CalibrationPage', () => ({
  get CalibrationPage() {
    throw new Error('chunk failed to load');
  },
}));

describe('App when the calibration chunk fails to load', () => {
  it('shows the calibration error and keeps the rest of the dashboard', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {});
    render(
      <Provider store={makeStore()}>
        <App />
      </Provider>,
    );
    expect(await screen.findByText('Nie udało się wczytać panelu kalibracji.')).toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: 'Ile alarmów, a ile przeoczeń?' })).toBeNull();
    const region = await screen.findByRole('region', { name: 'Podsumowanie' });
    expect(region).toHaveTextContent(`${summary.total} zgłoszeń`);
  });
});

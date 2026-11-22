import { render, screen, within } from '@testing-library/react';
import { Provider } from 'react-redux';
import { describe, expect, it, vi } from 'vitest';
import { App } from './App';
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
    window.location.hash = 'kalibracja';
    render(
      <Provider store={makeStore()}>
        <App />
      </Provider>,
    );
    expect(await screen.findByText('Nie udało się wczytać panelu kalibracji.')).toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: 'Ile alarmów, a ile przeoczeń?' })).toBeNull();
    // The header and its navigation stay, so the user can leave the broken page.
    const nav = screen.getByRole('navigation', { name: 'Sekcje' });
    expect(within(nav).getByRole('link', { name: 'Przegląd' })).toBeInTheDocument();
  });
});

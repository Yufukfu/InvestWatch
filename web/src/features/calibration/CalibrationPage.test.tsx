import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { Provider } from 'react-redux';
import { describe, expect, it } from 'vitest';
import { investWatchApi } from '../../api/generated';
import calM2 from '../../test/fixtures/calibration-M2.json';
import calM3 from '../../test/fixtures/calibration-M3.json';
import thresholds from '../../test/fixtures/thresholds.json';
import { server } from '../../test/setup';
import { makeStore, storeWrapper } from '../../test/store';
import { CalibrationPage } from './CalibrationPage';

const idx = (t: number) => String(calM2.points.findIndex((p) => p.threshold === t));

describe('CalibrationPage', () => {
  it('starts on M2 at the current threshold, previews without requests, and switches module', async () => {
    const asked: string[] = [];
    server.use(
      http.get('http://localhost/api/calibration', ({ request }) => {
        const m = new URL(request.url).searchParams.get('module')!;
        asked.push(m);
        return HttpResponse.json(m === 'M3' ? calM3 : calM2);
      }),
    );
    render(<CalibrationPage chartSize={{ width: 500, height: 240 }} />, { wrapper: storeWrapper() });
    const slider = await screen.findByRole('slider', { name: 'Próg dla M2' });
    expect(slider).toHaveValue(idx(0.5));
    fireEvent.change(slider, { target: { value: idx(0.7) } });
    expect(screen.getByRole('group', { name: 'Fałszywe alarmy (FP)' })).toHaveTextContent('obecnie 5');
    expect(asked).toEqual(['M2']);
    fireEvent.click(screen.getByRole('button', { name: 'M3 · Usługi bez zezwolenia' }));
    const m3 = await screen.findByRole('slider', { name: 'Próg dla M3' });
    expect(m3).toHaveAttribute('aria-valuetext', `próg ${calM3.current_threshold.toFixed(2)}`);
    expect(asked).toEqual(['M2', 'M3']);
  });

  it('saves M2 0.70 with the other thresholds unchanged and shows the new current threshold', async () => {
    let body: unknown;
    let current = calM2.current_threshold;
    server.use(
      http.get('http://localhost/api/calibration', () => HttpResponse.json({ ...calM2, current_threshold: current })),
      http.put('http://localhost/api/settings/thresholds', async ({ request }) => {
        body = await request.json();
        current = (body as { M2: number }).M2;
        return HttpResponse.json(body as object);
      }),
    );
    render(<CalibrationPage chartSize={{ width: 500, height: 240 }} />, { wrapper: storeWrapper() });
    const slider = await screen.findByRole('slider', { name: 'Próg dla M2' });
    await waitFor(() => expect(screen.getByRole('button', { name: 'Zapisz próg' })).toHaveAttribute('aria-disabled', 'true'));
    fireEvent.change(slider, { target: { value: idx(0.7) } });
    fireEvent.click(screen.getByRole('button', { name: 'Zapisz próg' }));
    await waitFor(() => expect(screen.getByText(/obecny próg: 0\.70/)).toBeInTheDocument());
    expect(body).toEqual({ ...thresholds, M2: 0.7 });
    expect(screen.getByRole('button', { name: 'Zapisz próg' })).toHaveAttribute('aria-disabled', 'true');
  });

  it('a rejected save keeps the current threshold and shows the error', async () => {
    server.use(http.put('http://localhost/api/settings/thresholds', () => HttpResponse.json({ error: 'x' }, { status: 422 })));
    render(<CalibrationPage chartSize={{ width: 500, height: 240 }} />, { wrapper: storeWrapper() });
    const slider = await screen.findByRole('slider', { name: 'Próg dla M2' });
    await waitFor(() => expect(screen.getByRole('button', { name: 'Zapisz próg' })).toHaveAttribute('aria-disabled', 'true'));
    fireEvent.change(slider, { target: { value: idx(0.7) } });
    fireEvent.click(screen.getByRole('button', { name: 'Zapisz próg' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Nie zapisano progu: serwer odrzucił wartość.');
    expect(screen.getByText(/obecny próg: 0\.50/)).toBeInTheDocument();
  });

  it('a threshold changed elsewhere moves the slider to the new current point', async () => {
    let current = 0.5;
    server.use(http.get('http://localhost/api/calibration', () => HttpResponse.json({ ...calM2, current_threshold: current })));
    const store = makeStore();
    render(
      <Provider store={store}>
        <CalibrationPage chartSize={{ width: 500, height: 240 }} />
      </Provider>,
    );
    const slider = await screen.findByRole('slider', { name: 'Próg dla M2' });
    fireEvent.change(slider, { target: { value: idx(0.9) } });
    current = 0.6;
    act(() => {
      store.dispatch(investWatchApi.util.invalidateTags(['calibration']));
    });
    await waitFor(() => expect(screen.getByRole('slider', { name: 'Próg dla M2' })).toHaveValue(idx(0.6)));
  });

  it('a save confirmation or error does not follow to another module', async () => {
    server.use(http.put('http://localhost/api/settings/thresholds', () => HttpResponse.json({ error: 'x' }, { status: 422 })));
    render(<CalibrationPage chartSize={{ width: 500, height: 240 }} />, { wrapper: storeWrapper() });
    const slider = await screen.findByRole('slider', { name: 'Próg dla M2' });
    await waitFor(() => expect(screen.getByRole('button', { name: 'Zapisz próg' })).toHaveAttribute('aria-disabled', 'true'));
    fireEvent.change(slider, { target: { value: idx(0.7) } });
    fireEvent.click(screen.getByRole('button', { name: 'Zapisz próg' }));
    await screen.findByRole('alert');
    fireEvent.click(screen.getByRole('button', { name: 'M1 · Finfluencerzy' }));
    await screen.findByRole('slider', { name: 'Próg dla M1' });
    expect(screen.queryByRole('alert')).toBeNull();
    expect(screen.queryByRole('status')).toBeNull();
  });

  it('keeps the selected threshold, not a position, when the curve changes shape', async () => {
    let points = calM2.points;
    server.use(http.get('http://localhost/api/calibration', () => HttpResponse.json({ ...calM2, points })));
    const store = makeStore();
    render(
      <Provider store={store}>
        <CalibrationPage chartSize={{ width: 500, height: 240 }} />
      </Provider>,
    );
    const slider = await screen.findByRole('slider', { name: 'Próg dla M2' });
    fireEvent.change(slider, { target: { value: idx(0.9) } });
    points = calM2.points.filter((p) => p.threshold >= 0.3);
    act(() => {
      store.dispatch(investWatchApi.util.invalidateTags(['calibration']));
    });
    await waitFor(() => expect(screen.getByRole('slider', { name: 'Próg dla M2' })).toHaveAttribute('max', String(points.length - 1)));
    expect(screen.getByRole('slider', { name: 'Próg dla M2' })).toHaveAttribute('aria-valuetext', 'próg 0.90');
  });

  it('falls back to the current point when the picked threshold is no longer on the curve', async () => {
    let points = calM2.points;
    server.use(http.get('http://localhost/api/calibration', () => HttpResponse.json({ ...calM2, points })));
    const store = makeStore();
    render(
      <Provider store={store}>
        <CalibrationPage chartSize={{ width: 500, height: 240 }} />
      </Provider>,
    );
    const slider = await screen.findByRole('slider', { name: 'Próg dla M2' });
    fireEvent.change(slider, { target: { value: idx(0.1) } });
    points = calM2.points.filter((p) => p.threshold >= 0.3);
    act(() => {
      store.dispatch(investWatchApi.util.invalidateTags(['calibration']));
    });
    await waitFor(() => expect(screen.getByRole('slider', { name: 'Próg dla M2' })).toHaveAttribute('aria-valuetext', 'próg 0.50'));
  });
});

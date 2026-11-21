import { act, renderHook, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { describe, expect, it } from 'vitest';
import { useGetFindingsQuery, useGetStatsSummaryQuery } from '../../../api/generated';
import calM2 from '../../../test/fixtures/calibration-M2.json';
import findings from '../../../test/fixtures/findings.json';
import summary from '../../../test/fixtures/summary.json';
import thresholds from '../../../test/fixtures/thresholds.json';
import { server } from '../../../test/setup';
import { storeWrapper } from '../../../test/store';
import { useCalibration, useThresholds } from './useCalibration';

describe('useCalibration', () => {
  it('requests the module and maps the curve', async () => {
    let asked = '';
    server.use(
      http.get('http://localhost/api/calibration', ({ request }) => {
        asked = new URL(request.url).searchParams.get('module') ?? '';
        return HttpResponse.json(calM2);
      }),
    );
    const { result } = renderHook(() => useCalibration('M2'), { wrapper: storeWrapper() });
    await waitFor(() => expect(result.current.view).toBeDefined());
    expect(asked).toBe('M2');
    expect(result.current.view).toEqual({
      module: 'M2',
      currentThreshold: calM2.current_threshold,
      labeledSamples: calM2.labeled_samples,
      points: calM2.points,
    });
  });

  it('reports an error', async () => {
    server.use(http.get('http://localhost/api/calibration', () => HttpResponse.error()));
    const { result } = renderHook(() => useCalibration('M1'), { wrapper: storeWrapper() });
    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.view).toBeUndefined();
  });
});

describe('useThresholds', () => {
  it('saves all three thresholds with one replaced, then refetches findings, stats and calibration', async () => {
    let body: unknown;
    const calls = { list: 0, summary: 0, calibration: 0 };
    let saved = { ...thresholds };
    server.use(
      http.get('http://localhost/api/findings', () => {
        calls.list += 1;
        return HttpResponse.json(findings);
      }),
      http.get('http://localhost/api/stats/summary', () => {
        calls.summary += 1;
        return HttpResponse.json(summary);
      }),
      http.get('http://localhost/api/calibration', () => {
        calls.calibration += 1;
        return HttpResponse.json(calM2);
      }),
      http.get('http://localhost/api/settings/thresholds', () => HttpResponse.json(saved)),
      http.put('http://localhost/api/settings/thresholds', async ({ request }) => {
        body = await request.json();
        saved = body as typeof saved;
        return HttpResponse.json(saved);
      }),
    );
    const { result } = renderHook(
      () => ({ t: useThresholds(), c: useCalibration('M2'), l: useGetFindingsQuery({}), s: useGetStatsSummaryQuery() }),
      { wrapper: storeWrapper() },
    );
    await waitFor(() => expect(result.current.t.thresholds).toEqual(thresholds));
    await waitFor(() => expect(calls).toEqual({ list: 1, summary: 1, calibration: 1 }));
    act(() => result.current.t.save('M2', 0.7));
    await waitFor(() => expect(result.current.t.saved).toBe(true));
    expect(body).toEqual({ ...thresholds, M2: 0.7 });
    await waitFor(() => expect(calls).toEqual({ list: 2, summary: 2, calibration: 2 }));
    await waitFor(() => expect(result.current.t.thresholds?.M2).toBe(0.7));
  });

  it('cannot save before the thresholds are known', () => {
    const { result } = renderHook(() => useThresholds(), { wrapper: storeWrapper() });
    expect(result.current.thresholds).toBeUndefined();
    expect(result.current.canSave).toBe(false);
  });

  it('gives a Polish error when the save is rejected', async () => {
    server.use(http.put('http://localhost/api/settings/thresholds', () => HttpResponse.json({ error: 'out of range' }, { status: 422 })));
    const { result } = renderHook(() => useThresholds(), { wrapper: storeWrapper() });
    await waitFor(() => expect(result.current.canSave).toBe(true));
    act(() => result.current.save('M1', 0.9));
    await waitFor(() => expect(result.current.error).toBe('Nie zapisano progu: serwer odrzucił wartość.'));
    expect(result.current.saved).toBe(false);
  });

  it('a network failure has its own message', async () => {
    server.use(http.put('http://localhost/api/settings/thresholds', () => HttpResponse.error()));
    const { result } = renderHook(() => useThresholds(), { wrapper: storeWrapper() });
    await waitFor(() => expect(result.current.canSave).toBe(true));
    act(() => result.current.save('M1', 0.9));
    await waitFor(() => expect(result.current.error).toBe('Nie zapisano progu: brak połączenia z serwerem.'));
  });
});

import { renderHook } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { useGetHealthQuery } from '../../../api/generated';
import { useHealth } from './useHealth';

// The generated hook is replaced so the polling option is asserted directly, without timers.
vi.mock('../../../api/generated', () => ({ useGetHealthQuery: vi.fn() }));

describe('useHealth polling', () => {
  beforeEach(() => {
    vi.mocked(useGetHealthQuery).mockReturnValue({ data: { status: 'ok', services: {} }, isError: false, isLoading: false } as never);
  });

  it('polls the health endpoint every 30 seconds', () => {
    renderHook(() => useHealth());
    expect(useGetHealthQuery).toHaveBeenCalledWith(undefined, { pollingInterval: 30_000 });
  });
});

import { act, renderHook } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { useUrlSearch } from './useUrlSearch';

describe('useUrlSearch', () => {
  it('reads the current search and pushes a new one', () => {
    window.history.replaceState(null, '', '/?module=M1');
    const { result } = renderHook(() => useUrlSearch());
    expect(result.current[0]).toBe('?module=M1');
    act(() => result.current[1]('?module=M2'));
    expect(result.current[0]).toBe('?module=M2');
    expect(window.location.search).toBe('?module=M2');
  });

  it('follows back and forward navigation', () => {
    window.history.replaceState(null, '', '/?page=1');
    const { result } = renderHook(() => useUrlSearch());
    act(() => {
      window.history.replaceState(null, '', '/?page=2');
      window.dispatchEvent(new PopStateEvent('popstate'));
    });
    expect(result.current[0]).toBe('?page=2');
  });

  it('writes an empty search as the bare path', () => {
    window.history.replaceState(null, '', '/?page=2');
    const { result } = renderHook(() => useUrlSearch());
    act(() => result.current[1](''));
    expect(window.location.search).toBe('');
    expect(result.current[0]).toBe('');
  });
});

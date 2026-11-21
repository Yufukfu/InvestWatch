import { act, renderHook } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { pushSearch, setSearchParam, useUrlSearch } from './useUrlSearch';

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

  it('replaces the history entry when asked, and pushes otherwise', () => {
    window.history.replaceState(null, '', '/');
    const { result } = renderHook(() => useUrlSearch());
    const start = window.history.length;
    act(() => result.current[1]('?q=a', { replace: true }));
    expect(window.history.length).toBe(start);
    expect(result.current[0]).toBe('?q=a');
    act(() => result.current[1]('?q=a&module=M1'));
    expect(window.history.length).toBe(start + 1);
    expect(result.current[0]).toBe('?q=a&module=M1');
  });

  it('setSearchParam keeps the other parameters and writes commas unescaped', () => {
    window.history.replaceState(null, '', '/?module=M1&status=new,in_review');
    setSearchParam('finding', 'abc');
    expect(window.location.search).toBe('?module=M1&status=new,in_review&finding=abc');
  });

  it('setSearchParam replaces the value in place', () => {
    window.history.replaceState(null, '', '/?finding=a&module=M1');
    setSearchParam('finding', 'b');
    expect(window.location.search).toBe('?finding=b&module=M1');
  });

  it('pushSearch keeps the path and the hash, and does nothing when the search is unchanged', () => {
    window.history.replaceState(null, '', '/dash#top?x=1');
    const start = window.history.length;
    pushSearch('?module=M2');
    expect(window.location.pathname).toBe('/dash');
    expect(window.location.hash).toBe('#top?x=1');
    expect(window.location.search).toBe('?module=M2');
    expect(window.history.length).toBe(start + 1);
    pushSearch('?module=M2');
    expect(window.history.length).toBe(start + 1);
  });

  it('pushSearch notifies subscribers of a write made outside React', () => {
    window.history.replaceState(null, '', '/');
    const { result } = renderHook(() => useUrlSearch());
    act(() => pushSearch('?finding=z', { replace: true }));
    expect(result.current[0]).toBe('?finding=z');
  });
});

import { useCallback, useSyncExternalStore } from 'react';

// The URL search string as React state, without a router: reads window.location.search, follows
// back/forward (popstate) and our own pushes. One screen does not justify a router dependency.
const CHANGE = 'iw:urlchange';

function subscribe(onChange: () => void) {
  window.addEventListener('popstate', onChange);
  window.addEventListener(CHANGE, onChange);
  return () => {
    window.removeEventListener('popstate', onChange);
    window.removeEventListener(CHANGE, onChange);
  };
}

const getSearch = () => window.location.search;

export type UrlWrite = (next: string, options?: { replace?: boolean }) => void;

// `replace` rewrites the current history entry (a settled text search); a discrete change pushes
// one, so the back button steps through views, not keystrokes.
export function pushSearch(next: string, options?: { replace?: boolean }): void {
  if (next === window.location.search) return;
  const url = `${window.location.pathname}${next}${window.location.hash}`;
  if (options?.replace) window.history.replaceState(null, '', url);
  else window.history.pushState(null, '', url);
  window.dispatchEvent(new Event(CHANGE));
}

// Sets one parameter and keeps the others (e.g. open a finding without losing the filters).
export function setSearchParam(name: string, value: string): void {
  const p = new URLSearchParams(window.location.search);
  p.set(name, value);
  const s = p.toString().replaceAll('%2C', ',');
  pushSearch(s ? `?${s}` : '');
}

export function useUrlSearch(): [string, UrlWrite] {
  const search = useSyncExternalStore(subscribe, getSearch, getSearch);
  const write = useCallback<UrlWrite>((next, options) => pushSearch(next, options), []);
  return [search, write];
}

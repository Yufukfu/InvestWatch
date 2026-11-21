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

export function useUrlSearch(): [string, (next: string) => void] {
  const search = useSyncExternalStore(subscribe, getSearch, getSearch);
  const push = useCallback((next: string) => {
    if (next === window.location.search) return;
    window.history.pushState(null, '', `${window.location.pathname}${next}${window.location.hash}`);
    window.dispatchEvent(new Event(CHANGE));
  }, []);
  return [search, push];
}

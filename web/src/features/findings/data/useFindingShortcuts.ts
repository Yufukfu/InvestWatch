import { useEffect, type RefObject } from 'react';
import { STATUSES, type FindingRow, type FindingStatus } from '../model';

// What the open detail offers the shortcuts. The detail owns the mutation, so a failed change shows
// the same error as one made with the mouse. `url` is already checked to be http or https.
export type ShortcutTarget = {
  status: FindingStatus;
  url: string | undefined;
  isSaving: boolean;
  setStatus: (status: FindingStatus) => void;
};

type Args = {
  rows: FindingRow[] | undefined;
  selectedId: string | undefined;
  select: (id: string) => void;
  targetRef: RefObject<ShortcutTarget | null>;
  focusSearch: () => void;
};

// Fields that take text, and anything editable: a shortcut there would eat what the user types.
function isTyping(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  // A radio or checkbox takes no text, so a shortcut there eats nothing (the status radios keep 1-5 working).
  if (target instanceof HTMLInputElement && ['radio', 'checkbox', 'button'].includes(target.type)) return false;
  if (['INPUT', 'SELECT', 'TEXTAREA'].includes(target.tagName)) return true;
  return target.closest('[contenteditable=""], [contenteditable="true"]') !== null;
}

// J/K move within the loaded page, 1-5 set the status of the open finding, O opens its source, / goes to
// the search field. Esc is not handled here: the detail's own two-step Escape stays the only handler.
export function useFindingShortcuts({ rows, selectedId, select, targetRef, focusSearch }: Args): void {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.ctrlKey || e.metaKey || e.altKey || e.defaultPrevented || isTyping(e.target)) return;
      const key = e.key.toLowerCase();
      const index = rows?.findIndex((r) => r.id === selectedId) ?? -1;

      if (key === 'j' && rows && rows.length > 0) {
        if (index === -1) select(rows[0].id);
        else if (index < rows.length - 1) select(rows[index + 1].id);
        return;
      }
      if (key === 'k') {
        if (rows && index > 0) select(rows[index - 1].id);
        return;
      }
      if (key === '/') {
        e.preventDefault();
        focusSearch();
        return;
      }

      const open = targetRef.current; // only set while a detail is mounted
      if (!open) return;
      if (key === 'o') {
        if (open.url) window.open(open.url, '_blank', 'noopener,noreferrer');
        return;
      }
      const next = /^[1-5]$/.test(key) ? STATUSES[Number(key) - 1] : undefined;
      if (next && next !== open.status && !open.isSaving) open.setStatus(next);
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [rows, selectedId, select, targetRef, focusSearch]);
}

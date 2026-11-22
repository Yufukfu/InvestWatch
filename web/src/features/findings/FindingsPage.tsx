import { useCallback, useEffect, useMemo, useRef, useState, type RefObject } from 'react';
import { createPortal } from 'react-dom';
import { BulkStatusBar } from './components/BulkStatusBar';
import { FindingDetailPanel } from './components/FindingDetailPanel';
import { FindingsFilters } from './components/FindingsFilters';
import { FindingsPager } from './components/FindingsPager';
import { FindingsTable, type RowSelection } from './components/FindingsTable';
import { safeHttpUrl } from './components/labels';
import { ModuleSwitcher } from './components/ModuleSwitcher';
import { ShortcutLegend } from './components/ShortcutLegend';
import { StatusEditor } from './components/StatusEditor';
import { useDocumentFindings } from './data/useDocumentFindings';
import { useFindingDetail } from './data/useFindingDetail';
import { useFindingShortcuts, type ShortcutTarget } from './data/useFindingShortcuts';
import { useBulkStatus } from './data/useBulkStatus';
import { serializeUrl } from './data/findingsUrl';
import { useFindings } from './data/useFindings';
import { useStatusChange } from './data/useStatusChange';
import type { FindingRow } from './model';

type DetailProps = {
  id: string;
  onClose: () => void;
  onSwitch: (id: string) => void;
  focusSwitcher: boolean;
  targetRef: RefObject<ShortcutTarget | null>;
};

function DetailContainer({ id, onClose, onSwitch, focusSwitcher, targetRef }: DetailProps) {
  const d = useFindingDetail(id);
  const change = useStatusChange(id);
  const siblings = useDocumentFindings(d.detail?.documentId);
  const [isDirty, setDirty] = useState(false);
  const switcher = <ModuleSwitcher options={siblings} currentId={id} onSelect={onSwitch} autoFocus={focusSwitcher} />;
  // The shortcuts act through this detail's own mutation, so an error shows here like a mouse change would.
  const { save, isSaving } = change;
  const status = d.detail?.status;
  const url = safeHttpUrl(d.detail?.url);
  useEffect(() => {
    targetRef.current = status ? { status, url, isSaving, isDirty, setStatus: (next) => save({ status: next }) } : null;
    return () => {
      targetRef.current = null;
    };
  }, [targetRef, status, url, isSaving, isDirty, save]);
  const editor = d.detail && (
    <StatusEditor
      status={d.detail.status}
      note={d.detail.note}
      onSave={change.save}
      isSaving={change.isSaving}
      saved={change.saved}
      error={change.error}
      onDirtyChange={setDirty}
    />
  );
  return <FindingDetailPanel {...d} onClose={onClose} statusEditor={editor} moduleSwitcher={switcher} />;
}

// Bulk selection belongs to one loaded list: it is stored with the list's URL (filters, sort, page), and
// any filter, sort or page change clears it. Only ids still in the
// loaded rows count, in row order, so it never exceeds the page size (at most 100, the API takes 200).
function useRowSelection(listKey: string, rows: FindingRow[] | undefined) {
  const [state, setState] = useState<{ key: string; ids: ReadonlySet<string> }>({ key: listKey, ids: new Set() });
  // Adjusting state while rendering (React's pattern for state derived from props): forget the old list's
  // selection at once, so returning to that list later does not bring it back.
  if (state.key !== listKey) setState({ key: listKey, ids: new Set() });
  const stored = state.ids;
  const selected = useMemo(() => (rows ?? []).filter((r) => stored.has(r.id)), [rows, stored]);
  const ids = useMemo(() => new Set(selected.map((r) => r.id)), [selected]);
  const clear = useCallback(() => setState({ key: listKey, ids: new Set() }), [listKey]);
  const selection: RowSelection = {
    ids,
    toggle: (id) => {
      const next = new Set(ids);
      if (!next.delete(id)) next.add(id);
      setState({ key: listKey, ids: next });
    },
    toggleAll: () => {
      const all = rows !== undefined && rows.length > 0 && rows.every((r) => ids.has(r.id));
      setState({ key: listKey, ids: all ? new Set() : new Set(rows?.map((r) => r.id)) });
    },
  };
  return { selected, selection, clear };
}

export function FindingsPage() {
  const f = useFindings();
  const targetRef = useRef<ShortcutTarget | null>(null);
  const focusSearch = useCallback(
    () => document.querySelector<HTMLInputElement>('.findings-panel input[type="search"]')?.focus(),
    [],
  );
  const { selected, selection, clear } = useRowSelection(serializeUrl(f.filters, undefined), f.rows);
  const bulk = useBulkStatus();
  const clearSelection = selected.length > 0 ? clear : undefined;
  useFindingShortcuts({ rows: f.rows, selectedId: f.selectedId, select: f.select, targetRef, focusSearch, clearSelection });
  // The finding opened from the module switcher; its panel puts focus back on the switcher.
  const [switchedTo, setSwitchedTo] = useState<string>();
  const switchTo = (id: string) => {
    setSwitchedTo(id);
    f.select(id);
  };
  return (
    <section className="panel findings-panel" aria-labelledby="findings-heading">
      <div className="panel-header">
        <h2 id="findings-heading">Zgłoszenia</h2>
        {f.isFetching && !f.isLoading && (
          // Visual only: the table carries aria-busy, so screen readers are not told every 10 s.
          <span className="muted" aria-hidden="true">
            Odświeżanie…
          </span>
        )}
      </div>
      <ShortcutLegend />
      <FindingsFilters filters={f.filters} onChange={f.setFilters} onReset={f.resetFilters} />
      <BulkStatusBar
        count={selected.length}
        onApply={(status) => {
          void bulk.apply(selected, status).then((ok) => {
            if (ok) clear();
          });
        }}
        onClear={clear}
        isSaving={bulk.isSaving}
        error={bulk.error}
        outcome={bulk.outcome}
        onDismiss={bulk.dismiss}
      />
      <FindingsTable
        rows={f.rows}
        total={f.total}
        sort={f.filters.sort}
        onSort={(sort) => f.setFilters({ sort })}
        selectedId={f.selectedId}
        onSelect={f.select}
        onReset={f.resetFilters}
        onFirstPage={() => f.setFilters({ page: 1 })}
        isLoading={f.isLoading}
        isFetching={f.isFetching}
        isError={f.isError}
        selection={selection}
      />
      {f.total !== undefined && f.total > 0 && (
        <FindingsPager
          page={f.filters.page}
          pageSize={f.filters.pageSize}
          total={f.total}
          onPage={(page) => f.setFilters({ page })}
          onPageSize={(pageSize) => f.setFilters({ pageSize })}
        />
      )}
      {f.selectedId &&
        // Portal: the dialog sits outside the page, so the page can be made inert behind it.
        createPortal(
          <div className="detail-layer">
            <div className="detail-backdrop" aria-hidden="true" onClick={() => f.select(undefined)} />
            {/* key: a new selection remounts the panel, so focus handling restarts per finding. */}
            <DetailContainer
              key={f.selectedId}
              id={f.selectedId}
              onClose={() => f.select(undefined)}
              onSwitch={switchTo}
              focusSwitcher={switchedTo === f.selectedId}
              targetRef={targetRef}
            />
          </div>,
          document.body,
        )}
    </section>
  );
}

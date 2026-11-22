import { useCallback, useEffect, useRef, type RefObject } from 'react';
import { createPortal } from 'react-dom';
import { FindingDetailPanel } from './components/FindingDetailPanel';
import { FindingsFilters } from './components/FindingsFilters';
import { FindingsPager } from './components/FindingsPager';
import { FindingsTable } from './components/FindingsTable';
import { safeHttpUrl } from './components/labels';
import { ShortcutLegend } from './components/ShortcutLegend';
import { StatusEditor } from './components/StatusEditor';
import { useFindingDetail } from './data/useFindingDetail';
import { useFindingShortcuts, type ShortcutTarget } from './data/useFindingShortcuts';
import { useFindings } from './data/useFindings';
import { useStatusChange } from './data/useStatusChange';

function DetailContainer({ id, onClose, targetRef }: { id: string; onClose: () => void; targetRef: RefObject<ShortcutTarget | null> }) {
  const d = useFindingDetail(id);
  const change = useStatusChange(id);
  // The shortcuts act through this detail's own mutation, so an error shows here like a mouse change would.
  const { save, isSaving } = change;
  const status = d.detail?.status;
  const url = safeHttpUrl(d.detail?.url);
  useEffect(() => {
    targetRef.current = status ? { status, url, isSaving, setStatus: (next) => save({ status: next }) } : null;
    return () => {
      targetRef.current = null;
    };
  }, [targetRef, status, url, isSaving, save]);
  const editor = d.detail && (
    <StatusEditor
      status={d.detail.status}
      note={d.detail.note}
      onSave={change.save}
      isSaving={change.isSaving}
      saved={change.saved}
      error={change.error}
    />
  );
  return <FindingDetailPanel {...d} onClose={onClose} statusEditor={editor} />;
}

export function FindingsPage() {
  const f = useFindings();
  const targetRef = useRef<ShortcutTarget | null>(null);
  const focusSearch = useCallback(
    () => document.querySelector<HTMLInputElement>('.findings-panel input[type="search"]')?.focus(),
    [],
  );
  useFindingShortcuts({ rows: f.rows, selectedId: f.selectedId, select: f.select, targetRef, focusSearch });
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
            <DetailContainer key={f.selectedId} id={f.selectedId} onClose={() => f.select(undefined)} targetRef={targetRef} />
          </div>,
          document.body,
        )}
    </section>
  );
}

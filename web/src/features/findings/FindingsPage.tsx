import { FindingDetailPanel } from './components/FindingDetailPanel';
import { FindingsFilters } from './components/FindingsFilters';
import { FindingsPager } from './components/FindingsPager';
import { FindingsTable } from './components/FindingsTable';
import { StatusEditor } from './components/StatusEditor';
import { useFindingDetail } from './data/useFindingDetail';
import { useFindings } from './data/useFindings';
import { useStatusChange } from './data/useStatusChange';

function DetailContainer({ id, onClose }: { id: string; onClose: () => void }) {
  const d = useFindingDetail(id);
  const change = useStatusChange(id);
  const editor = d.detail && (
    // key: once the API returns the saved values, the form restarts from them.
    <StatusEditor
      key={`${d.detail.status}|${d.detail.note ?? ''}`}
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
  return (
    <section className="panel findings-panel" aria-labelledby="findings-heading">
      <div className="panel-header">
        <h2 id="findings-heading">Zgłoszenia</h2>
        {f.isFetching && !f.isLoading && (
          <span className="muted" role="status">
            Odświeżanie…
          </span>
        )}
      </div>
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
      {f.selectedId && (
        <>
          <div className="detail-backdrop" aria-hidden="true" onClick={() => f.select(undefined)} />
          {/* key: a new selection remounts the panel, so focus handling restarts per finding. */}
          <DetailContainer key={f.selectedId} id={f.selectedId} onClose={() => f.select(undefined)} />
        </>
      )}
    </section>
  );
}

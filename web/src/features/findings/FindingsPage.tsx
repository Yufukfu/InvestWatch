import { useState } from 'react';
import { createPortal } from 'react-dom';
import { FindingDetailPanel } from './components/FindingDetailPanel';
import { FindingsFilters } from './components/FindingsFilters';
import { FindingsPager } from './components/FindingsPager';
import { FindingsTable } from './components/FindingsTable';
import { ModuleSwitcher } from './components/ModuleSwitcher';
import { StatusEditor } from './components/StatusEditor';
import { useDocumentFindings } from './data/useDocumentFindings';
import { useFindingDetail } from './data/useFindingDetail';
import { useFindings } from './data/useFindings';
import { useStatusChange } from './data/useStatusChange';

type DetailProps = { id: string; onClose: () => void; onSwitch: (id: string) => void; focusSwitcher: boolean };

function DetailContainer({ id, onClose, onSwitch, focusSwitcher }: DetailProps) {
  const d = useFindingDetail(id);
  const change = useStatusChange(id);
  const siblings = useDocumentFindings(d.detail?.documentId);
  const switcher = <ModuleSwitcher options={siblings} currentId={id} onSelect={onSwitch} autoFocus={focusSwitcher} />;
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
  return <FindingDetailPanel {...d} onClose={onClose} statusEditor={editor} moduleSwitcher={switcher} />;
}

export function FindingsPage() {
  const f = useFindings();
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
            <DetailContainer
              key={f.selectedId}
              id={f.selectedId}
              onClose={() => f.select(undefined)}
              onSwitch={switchTo}
              focusSwitcher={switchedTo === f.selectedId}
            />
          </div>,
          document.body,
        )}
    </section>
  );
}

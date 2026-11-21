import { useId, useState } from 'react';
import { STATUSES, type FindingStatus } from '../model';
import { STATUS_LABEL } from './labels';

type Props = {
  status: FindingStatus;
  note: string | null | undefined;
  onSave: (patch: { status?: FindingStatus; note?: string | null }) => void;
  isSaving: boolean;
  saved: boolean;
  error: string | undefined;
};

// Any of the five statuses may be chosen; the contract defines no transition graph, the API decides.
export function StatusEditor({ status, note, onSave, isSaving, saved, error }: Props) {
  const id = useId();
  const [nextStatus, setNextStatus] = useState<FindingStatus>(status);
  const [text, setText] = useState(note ?? '');
  const nextNote = text.trim() === '' ? null : text.trim();
  const statusChanged = nextStatus !== status;
  const noteChanged = nextNote !== (note ?? null);

  return (
    <form
      className="status-editor"
      aria-label="Zmiana statusu"
      onSubmit={(e) => {
        e.preventDefault();
        if (!statusChanged && !noteChanged) return;
        onSave({ ...(statusChanged ? { status: nextStatus } : {}), ...(noteChanged ? { note: nextNote } : {}) });
      }}
    >
      <div className="field">
        <label htmlFor={`${id}-status`}>Status</label>
        <select
          id={`${id}-status`}
          value={nextStatus}
          disabled={isSaving}
          onChange={(e) => setNextStatus(e.target.value as FindingStatus)}
        >
          {STATUSES.map((s) => (
            <option key={s} value={s}>
              {STATUS_LABEL[s]}
            </option>
          ))}
        </select>
      </div>
      <div className="field">
        <label htmlFor={`${id}-note`}>Notatka</label>
        <textarea id={`${id}-note`} value={text} disabled={isSaving} maxLength={2000} onChange={(e) => setText(e.target.value)} />
      </div>
      <div className="status-actions">
        <button type="submit" className="btn btn-primary" disabled={isSaving || (!statusChanged && !noteChanged)}>
          {isSaving ? 'Zapisywanie…' : 'Zapisz'}
        </button>
        {error && <p role="alert">Nie udało się zapisać zmiany: {error}</p>}
        {saved && !error && (
          <p role="status" className="saved">
            Zapisano.
          </p>
        )}
      </div>
    </form>
  );
}

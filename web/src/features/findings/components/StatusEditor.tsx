import { useId, useState } from 'react';
import { STATUSES, type FindingStatus } from '../model';
import { STATUS_LABEL } from './labels';

type Props = {
  status: FindingStatus;
  note: string | null | undefined;
  onSave: (patch: { status?: FindingStatus; note?: string | null }) => void;
  isSaving: boolean;
  saved: boolean;
  error: { message: string; detail: string | undefined } | undefined;
};

// Any of the five statuses may be chosen; the contract defines no transition graph, the API decides.
export function StatusEditor({ status, note, onSave, isSaving, saved, error }: Props) {
  const id = useId();
  const [nextStatus, setNextStatus] = useState<FindingStatus>(status);
  const [text, setText] = useState(note ?? '');
  // New saved values from the API (after a save or a refetch) reset the form in place: no re-mount,
  // so keyboard focus stays where it was, inside the dialog.
  const [saved0, setSaved0] = useState({ status, note });
  if (saved0.status !== status || saved0.note !== note) {
    setSaved0({ status, note });
    setNextStatus(status);
    setText(note ?? '');
  }
  const nextNote = text.trim() === '' ? null : text.trim();
  const statusChanged = nextStatus !== status;
  const noteChanged = nextNote !== (note ?? null);

  return (
    <form
      className="status-editor"
      aria-label="Zmiana statusu"
      onSubmit={(e) => {
        e.preventDefault();
        if (isSaving || (!statusChanged && !noteChanged)) return;
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
        {/* aria-disabled, not disabled: a disabled button drops keyboard focus to <body> (out of the
            dialog) the moment a save starts or completes; onSubmit ignores the click instead. */}
        <button type="submit" className="btn btn-primary" aria-disabled={isSaving || (!statusChanged && !noteChanged)}>
          {isSaving ? 'Zapisywanie…' : 'Zapisz'}
        </button>
        {/* Both live regions are always in the DOM, so a new message is announced. */}
        <div className="save-error" role="alert">
          {error && <p>Nie udało się zapisać zmiany: {error.message}</p>}
          {error?.detail && (
            <p className="muted">
              Odpowiedź serwera: <span lang="en">{error.detail}</span>
            </p>
          )}
        </div>
        <p role="status" className="saved">
          {saved ? 'Zapisano.' : ''}
        </p>
      </div>
    </form>
  );
}

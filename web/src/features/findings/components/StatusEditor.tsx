import { useEffect, useId, useState } from 'react';
import { STATUSES, type FindingStatus } from '../model';
import { STATUS_LABEL } from './labels';

type Props = {
  status: FindingStatus;
  note: string | null | undefined;
  onSave: (patch: { status?: FindingStatus; note?: string | null }) => void;
  isSaving: boolean;
  saved: boolean;
  error: { message: string; detail: string | undefined } | undefined;
  // True while the form differs from the saved values, so a shortcut does not overwrite the draft.
  onDirtyChange?: (dirty: boolean) => void;
};

// Any of the five statuses may be chosen; the contract defines no transition graph, the API decides.
export function StatusEditor({ status, note, onSave, isSaving, saved, error, onDirtyChange }: Props) {
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
  const dirty = statusChanged || noteChanged;
  useEffect(() => {
    onDirtyChange?.(dirty);
    return () => onDirtyChange?.(false);
  }, [dirty, onDirtyChange]);

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
      <fieldset className="field field-status" role="radiogroup">
        <legend>Status</legend>
        <div className="chips">
          {STATUSES.map((s) => (
            <label key={s} className="chip">
              {/* aria-disabled, not disabled: a disabled radio drops keyboard focus out of the dialog while saving. */}
              <input
                type="radio"
                name={`${id}-status`}
                value={s}
                checked={nextStatus === s}
                aria-disabled={isSaving}
                onChange={() => {
                  if (!isSaving) setNextStatus(s);
                }}
              />
              <span>{STATUS_LABEL[s]}</span>
            </label>
          ))}
        </div>
      </fieldset>
      <div className="field">
        <label htmlFor={`${id}-note`}>Notatka</label>
        <textarea id={`${id}-note`} value={text} disabled={isSaving} maxLength={2000} onChange={(e) => setText(e.target.value)} />
      </div>
      <div className="status-actions">
        {/* aria-disabled, not disabled: a disabled button drops keyboard focus to <body> (out of the
            dialog) the moment a save starts or completes; onSubmit ignores the click instead. */}
        <button type="submit" className="btn btn-primary" aria-disabled={isSaving || (!statusChanged && !noteChanged)}>
          {isSaving ? 'Zapisywanie…' : 'Zapisz decyzję'}
        </button>
        {/* Both live regions are always in the DOM, so a new message is announced. */}
        <div className="save-error" role="alert">
          {error && <p>Nie udało się zapisać zmiany: {error.message}</p>}
          {error?.detail && (
            <p className="muted">
              {/* The server's own text: alone in a dir="auto" span, so a bidi control cannot reorder the label. */}
              Odpowiedź serwera:{' '}
              <span lang="en" dir="auto">
                {error.detail}
              </span>
            </p>
          )}
        </div>
        <p role="status" className="saved">
          {saved ? `Zapisano. Status: ${STATUS_LABEL[status]}.` : ''}
        </p>
      </div>
    </form>
  );
}

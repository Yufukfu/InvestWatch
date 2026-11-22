import type { RescanView } from '../model';
import { formatUtc } from './labels';

// Re-scan state of the finding's page (issue #71): a text badge plus one line. The values come from
// `parseRescan`, which keeps only a known state, a UUID id and an ISO time; they are rendered as text.
export function RescanNotice({ rescan }: { rescan: RescanView | undefined }) {
  if (!rescan) return null;
  const checked = rescan.checkedAt && <> Sprawdzono: {formatUtc(rescan.checkedAt)}.</>;
  if (rescan.state === 'changed') {
    return (
      <p className="rescan rescan-changed">
        <span className="rescan-badge">Zmieniona</span> Strona zmieniła się od tego zgłoszenia.
        {rescan.latestDocumentId && (
          <>
            {' '}
            Nowsza wersja: dokument <code>{rescan.latestDocumentId}</code>.
          </>
        )}
        {checked}
      </p>
    );
  }
  return (
    <p className="rescan rescan-removed">
      <span className="rescan-badge">Usunięta</span> Strona została usunięta po tym zgłoszeniu.
      {checked}
    </p>
  );
}

import { useId } from 'react';
import { groupThousands } from './labels';

type Props = {
  /** GET /findings/export with the filters to export. */
  href: string;
  /** Row cap of the export. */
  cap: number;
  /** Total of the current list; undefined while loading, after an error or off the findings page. */
  total: number | undefined;
  /** True when the export ignores the findings filters (another page is shown). */
  allFindings: boolean;
};

// A plain link: the API answers with a CSV attachment, so the browser downloads it. CSV is the only format.
export function ExportReportLink({ href, cap, total, allFindings }: Props) {
  const noteId = useId();
  const truncated = total !== undefined && total > cap;
  const scope = allFindings ? 'Wszystkie zgłoszenia, bez filtrów. ' : '';
  return (
    <>
      <a className="btn btn-outline" href={href} download aria-describedby={noteId}>
        Eksportuj raport
      </a>
      <span id={noteId} className="export-report-note">
        {scope}
        {truncated
          ? `CSV zawiera tylko pierwsze ${groupThousands(cap)} z ${groupThousands(total)} zgłoszeń.`
          : `CSV, maks. ${groupThousands(cap)} wierszy.`}
      </span>
    </>
  );
}

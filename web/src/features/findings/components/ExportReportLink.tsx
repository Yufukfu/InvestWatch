import { groupThousands } from './labels';

type Props = {
  /** GET /findings/export with the current list filters. */
  href: string;
  /** Row cap of the export. */
  cap: number;
  /** Total of the current list; undefined while loading or after an error. */
  total: number | undefined;
};

// A plain link: the API answers with a CSV attachment, so the browser downloads it.
export function ExportReportLink({ href, cap, total }: Props) {
  const truncated = total !== undefined && total > cap;
  return (
    <div className="export-report">
      <a className="btn btn-outline" href={href} download aria-describedby="export-report-note">
        Eksportuj raport
      </a>
      <span id="export-report-note" className="export-report-note">
        {truncated
          ? `CSV zawiera tylko pierwsze ${groupThousands(cap)} z ${groupThousands(total)} zgłoszeń.`
          : `CSV, maks. ${groupThousands(cap)} wierszy.`}
      </span>
    </div>
  );
}

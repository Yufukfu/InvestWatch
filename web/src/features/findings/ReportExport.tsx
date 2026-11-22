import { ExportReportLink } from './components/ExportReportLink';
import { EXPORT_ROW_CAP } from './data/findingsUrl';
import { useReportExport } from './data/useReportExport';

// "Eksportuj raport" in the app header (Paper mockup, desktop-1440): the current findings list on the
// findings page, every finding elsewhere.
export function ReportExport({ onFindingsPage }: { onFindingsPage: boolean }) {
  const r = useReportExport(onFindingsPage);
  return <ExportReportLink href={r.href} cap={EXPORT_ROW_CAP} total={r.total} allFindings={r.scope === 'all'} />;
}

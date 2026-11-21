import { FindingsTable } from './components/FindingsTable';
import { useFindings } from './data/useFindings';

export function FindingsPage() {
  const { rows, isLoading, isError } = useFindings();
  return <FindingsTable rows={rows} isLoading={isLoading} isError={isError} />;
}

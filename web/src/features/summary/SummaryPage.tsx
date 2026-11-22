import { useStartTriage } from '../findings/data/useFindings';
import { SummaryCards } from './components/SummaryCards';
import { useSummary } from './data/useSummary';

export function SummaryPage() {
  return <SummaryCards summary={useSummary()} onStartTriage={useStartTriage()} />;
}

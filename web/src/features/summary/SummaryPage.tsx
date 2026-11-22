import { useState } from 'react';
import { useStartTriage } from '../findings/data/useFindings';
import { SummaryCards } from './components/SummaryCards';
import { useSummary } from './data/useSummary';
import { formatDay } from './model';

export function SummaryPage() {
  // The day the page was opened; the overview does not roll over at midnight on its own.
  const [asOf] = useState(() => formatDay(new Date()));
  return <SummaryCards summary={useSummary()} asOf={asOf} onStartTriage={useStartTriage()} />;
}

import { HealthBadge } from './components/HealthBadge';
import { useHealth } from './data/useHealth';

export function HealthPage() {
  const { state } = useHealth();
  return <HealthBadge state={state} />;
}

import type { RiskLevel } from '../model';
import { RISK_LABEL } from './labels';

// Risk is text plus colour, never colour alone (web-dashboard rules).
export function RiskBadge({ level }: { level: RiskLevel | undefined }) {
  if (!level) return <span className="risk risk-none">Brak danych</span>;
  return <span className={`risk risk-${level}`}>{RISK_LABEL[level]}</span>;
}

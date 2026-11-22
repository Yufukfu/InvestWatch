// Types only, plus one formatter: the summary is a flat DTO, so no mapper (ADR 0204).
export type ModuleCount = { module: string; count: number };
// M2 findings and those matched to a KNF register entry (contracts 1.3.0); undefined from an older server.
export type M2CoverageCounts = { total: number; registryMatched: number };
export type SummaryCounts = {
  total: number;
  highRisk: number;
  newCount: number;
  byModule: ModuleCount[];
  m2Coverage?: M2CoverageCounts;
};

// The day in the overview eyebrow: dd.mm.rrrr in the viewer's local time.
export function formatDay(day: Date): string {
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${pad(day.getDate())}.${pad(day.getMonth() + 1)}.${day.getFullYear()}`;
}

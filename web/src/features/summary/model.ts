// Types only: the summary is a flat DTO, so no mapper (ADR 0204).
export type ModuleCount = { module: string; count: number };
export type SummaryCounts = { total: number; highRisk: number; newCount: number; byModule: ModuleCount[] };

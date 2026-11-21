// App-owned view model for a finding row. Components depend on this, not on the generated DTO,
// so a change of the API client or of unused DTO fields does not reach them (ADR 0204).
export type FindingModule = 'M1' | 'M2' | 'M3';
export type FindingStatus = 'new' | 'in_review' | 'confirmed' | 'false_positive' | 'closed';

export type FindingRow = {
  id: string;
  module: FindingModule;
  title: string;
  platform: string;
  score: number;
  status: FindingStatus;
};

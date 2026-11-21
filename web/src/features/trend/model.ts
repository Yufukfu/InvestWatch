// Types only: the trend DTO is flat, so no mapper (ADR 0204). Shared by the data hook and the chart.
export type TrendBucket = 'hour' | 'day';

// App-owned shape: a count may be absent and is then drawn as 0.
export type TrendPoint = { t: string; M1?: number; M2?: number; M3?: number };

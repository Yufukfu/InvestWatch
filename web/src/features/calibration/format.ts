// Every number the calibration panel and chart show uses pl-PL, so 0,70 and 85,7% read the same way.
const THRESHOLD = new Intl.NumberFormat('pl-PL', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const PERCENT = new Intl.NumberFormat('pl-PL', { style: 'percent', maximumFractionDigits: 1 });

export const formatThreshold = (v: number): string => THRESHOLD.format(v);
export const formatPercent = (v: number): string => PERCENT.format(v);

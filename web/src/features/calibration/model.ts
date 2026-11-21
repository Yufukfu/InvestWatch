export type CalibrationModule = 'M1' | 'M2' | 'M3';
export const CALIBRATION_MODULES: readonly CalibrationModule[] = ['M2', 'M1', 'M3'];

// One point of GET /calibration, exactly as the API returns it.
export type CalibrationPoint = {
  threshold: number;
  tp: number;
  fp: number;
  fn: number;
  tn: number;
  precision: number;
  recall: number;
  f1?: number;
};

export type CalibrationView = {
  module: CalibrationModule;
  currentThreshold: number;
  labeledSamples: number;
  points: CalibrationPoint[];
};

// Which existing point the slider starts on: the one nearest the saved threshold (a selection, no metric).
export function nearestIndex(points: CalibrationPoint[], threshold: number): number {
  let best = -1;
  for (let i = 0; i < points.length; i++) {
    if (best === -1 || Math.abs(points[i].threshold - threshold) < Math.abs(points[best].threshold - threshold)) best = i;
  }
  return best;
}

// Label side of the two markers: the lower threshold's label goes left, the higher one's right,
// so the two labels never sit on top of each other whichever threshold is larger.
export type LabelSide = 'insideTopLeft' | 'insideTopRight';
export function markerSides(current: number, selected: number): { current: LabelSide; selected: LabelSide } {
  return current <= selected
    ? { current: 'insideTopLeft', selected: 'insideTopRight' }
    : { current: 'insideTopRight', selected: 'insideTopLeft' };
}

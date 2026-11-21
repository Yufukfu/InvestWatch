import { describe, expect, it } from 'vitest';
import { markerSides, nearestIndex } from './model';

const pts = [0.3, 0.5, 0.7].map((threshold) => ({ threshold, tp: 0, fp: 0, fn: 0, tn: 0, precision: 0, recall: 0 }));

describe('markerSides', () => {
  // Recharts anchors an `insideTopRight` label at its line's end (text runs left) and `insideTopLeft`
  // at its start (text runs right): the lower marker gets TopRight so the two labels point apart.
  it('turns the two marker labels away from each other', () => {
    expect(markerSides(0.5, 0.7)).toEqual({ current: 'insideTopRight', selected: 'insideTopLeft' });
    expect(markerSides(0.7, 0.5)).toEqual({ current: 'insideTopLeft', selected: 'insideTopRight' });
  });
});

describe('nearestIndex', () => {
  it('finds the exact point', () => {
    expect(nearestIndex(pts, 0.5)).toBe(1);
  });
  it('finds the nearest point for a threshold off the curve', () => {
    expect(nearestIndex(pts, 0.62)).toBe(2);
    expect(nearestIndex(pts, 0.58)).toBe(1);
    expect(nearestIndex(pts, 0)).toBe(0);
    expect(nearestIndex(pts, 1)).toBe(2);
  });
  it('on an exact tie picks the lower threshold', () => {
    const two = [0.25, 0.75].map((threshold) => ({ ...pts[0], threshold }));
    expect(nearestIndex(two, 0.5)).toBe(0);
  });
  it('returns -1 for no points', () => {
    expect(nearestIndex([], 0.5)).toBe(-1);
  });
});

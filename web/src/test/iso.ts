// The expected form of a plain title inside a screen-reader string: wrapped in FSI (U+2068) and PDI (U+2069).
// Written out here, not taken from `format/bidi`, so a broken `isolate()` cannot also fix the expectation.
export const iso = (title: string) => `\u2068${title}\u2069`;

// Plain-text `dir="auto"`: wraps a value in U+2068 FIRST STRONG ISOLATE and U+2069 POP DIRECTIONAL ISOLATE,
// so a bidi control inside it cannot reorder the text around it. For strings where no element can carry
// `dir`, such as `aria-label`s and live-region text.
export function isolate(text: string): string {
  return `\u2068${text}\u2069`;
}

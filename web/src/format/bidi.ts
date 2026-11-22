const FSI = '\u2068';
const PDI = '\u2069';
// LRI, RLI and FSI open an isolate; PDI closes the innermost open one (UAX #9).
const OPENERS = new Set(['\u2066', '\u2067', '\u2068']);
// Bidi class B (paragraph separators): each ends every open isolate, so it would split ours.
const PARAGRAPH_SEPARATORS = new Set(['\n', '\r', '\u001C', '\u001D', '\u001E', '\u0085', '\u2029']);

// The plain-text counterpart of a `dir="auto"` element, for strings that have no element of their own:
// an `aria-label`, a live announcement. Accessible names and announcements reach assistive technology as
// one flat string, so the isolate has to be characters in the string.
// Untrusted text is balanced first, so it cannot leave the isolate: a PDI with no opener is dropped (it
// would close ours early and let a following U+202E reorder the UI text after it), an isolate it leaves
// open is closed before our PDI, and a paragraph separator becomes a space. Embeddings and overrides
// (U+202A..U+202E) need no closing: our PDI ends them (UAX #9, X6a). Every other character is kept.
export function isolate(text: string): string {
  let open = 0;
  let out = '';
  for (const ch of text) {
    if (OPENERS.has(ch)) open++;
    else if (ch === PDI) {
      if (open === 0) continue;
      open--;
    } else if (PARAGRAPH_SEPARATORS.has(ch)) {
      out += ' ';
      continue;
    }
    out += ch;
  }
  return FSI + out + PDI.repeat(open) + PDI;
}

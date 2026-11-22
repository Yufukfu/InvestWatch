"""The text blocks of a rendered page, measured in the browser and cleaned here.

The measurement runs in an isolated world of the page's main frame (own JavaScript globals, shared DOM), so a page
cannot replace `getComputedStyle` or the array methods the script uses. Whatever comes back is still treated as
untrusted: every field is checked and fitted to the contract's `block` shape before it leaves this module.
"""

import math
import re
from dataclasses import dataclass

MAX_TEXT_CHARS = 4000
DEFAULT_MAX_BLOCKS = 600
WORLD_NAME = "iw-measure"
REGIONS = ("main", "header", "footer", "legal", "aside", "overlay")
_COLOR = re.compile(r"#[0-9a-f]{6}")
_UNWANTED = re.compile("[\x00\ud800-\udfff]")

# Placement words only, never content words (`risk`, `ryzyk`, `ostrzezen`, `warning`): a risk box below the fold is
# not legal text. Matched as case-insensitive substrings of the id, class and accessible name, diacritics folded.
PLACEMENT_WORDS = (
    "legal", "prawn", "klauzul", "objasnien", "warunk", "regulacj", "regulamin", "zastrzezen", "przypis", "knf",
    "disclaimer", "disclosure", "footnote", "endnote", "fine-print", "fineprint", "small-print",
    "important-information", "important-notice", "terms", "tnc", "notice", "compliance", "regulatory", "imprint",
    "impressum",
)

# Runs with one argument: {words, maxBlocks, maxText}. Returns {blocks, truncated}. No logging, no network.
MEASURE_SCRIPT = r"""
(opts) => {
  const SKIP = 'script,style,noscript,template';
  const fold = (s) => (s || '').toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '');
  const viewportHeight = window.innerHeight;
  const styleOf = (el) => getComputedStyle(el);
  const isBlockLevel = (el) => { const d = styleOf(el).display; return !(d.startsWith('inline') || d === 'contents'); };

  const parseColor = (value) => {
    const m = /^rgba?\(\s*(\d+(?:\.\d+)?)[ ,]+(\d+(?:\.\d+)?)[ ,]+(\d+(?:\.\d+)?)(?:\s*[,/]\s*(\d*\.?\d+%?))?\s*\)$/.exec(value || '');
    if (!m) return null;
    let a = 1;
    if (m[4] !== undefined) a = m[4].endsWith('%') ? parseFloat(m[4]) / 100 : parseFloat(m[4]);
    return { r: +m[1], g: +m[2], b: +m[3], a };
  };
  const over = (top, bottom) => ({
    r: top.r * top.a + bottom.r * (1 - top.a), g: top.g * top.a + bottom.g * (1 - top.a),
    b: top.b * top.a + bottom.b * (1 - top.a), a: 1,
  });
  const hex = (c) => '#' + [c.r, c.g, c.b].map((v) => Math.max(0, Math.min(255, Math.round(v))).toString(16).padStart(2, '0')).join('');

  const backgroundOf = (el) => {
    const layers = [];
    for (let a = el; a; a = a.parentElement) {
      const s = styleOf(a);
      if (s.backgroundImage !== 'none') return null;
      const c = parseColor(s.backgroundColor);
      if (c === null && s.backgroundColor !== 'rgba(0, 0, 0, 0)' && s.backgroundColor !== 'transparent') return null;
      if (c && c.a > 0) layers.push(c);
      if (c && c.a === 1) break;
    }
    let result = { r: 255, g: 255, b: 255, a: 1 };
    if (layers.length && layers[layers.length - 1].a === 1) result = layers.pop();
    while (layers.length) result = over(layers.pop(), result);
    return result;
  };

  const isVisible = (el, rect) => {
    const ok = el.checkVisibility({ opacityProperty: true, visibilityProperty: true, checkOpacity: true, checkVisibilityCSS: true });
    return ok && rect.width > 0 && rect.height > 0;
  };

  const inClosedDetails = (el) => {
    for (let a = el; a; a = a.parentElement) {
      if (a.tagName === 'DETAILS' && !a.open) {
        const summary = a.querySelector(':scope > summary');
        if (!(summary && summary.contains(el))) return true;
      }
    }
    return false;
  };
  const controlledByCollapsed = (el) => {
    for (let a = el; a; a = a.parentElement) {
      if (!a.id) continue;
      const control = document.querySelector('[aria-controls~="' + CSS.escape(a.id) + '"][aria-expanded="false"]');
      if (control && control.checkVisibility()) return true;
    }
    return false;
  };

  const nameOf = (a) => {
    const labelled = (a.getAttribute('aria-labelledby') || '').split(/\s+/).map((id) => {
      const n = id && document.getElementById(id); return n ? n.textContent : '';
    }).join(' ');
    return [a.id, a.getAttribute('class'), a.getAttribute('aria-label'), labelled].join(' ');
  };
  const headingOf = (a) => {
    const h = a.querySelector(':scope > h1, :scope > h2, :scope > h3, :scope > h4, :scope > h5, :scope > h6');
    return h ? h.textContent : '';
  };
  const LEGAL_ROLES = new Set(['note', 'doc-footnote', 'doc-endnotes']);
  const regionOf = (from) => {
    let legal = false, footer = false, header = false, aside = false;
    for (let a = from; a; a = a.parentElement) {
      const tag = a.tagName, role = a.getAttribute('role') || '';
      if (styleOf(a).position === 'fixed' || (tag === 'DIALOG' && a.hasAttribute('open')) || a.getAttribute('aria-modal') === 'true') return 'overlay';
      if (tag === 'SMALL' || LEGAL_ROLES.has(role)) legal = true;
      const text = fold(nameOf(a)) + (tag === 'BODY' || tag === 'HTML' || tag === 'MAIN' ? '' : ' ' + fold(headingOf(a)));
      if (opts.words.some((w) => text.includes(w))) legal = true;
      if (tag === 'FOOTER' || role === 'contentinfo') footer = true;
      if (tag === 'HEADER' || role === 'banner') header = true;
      if (tag === 'ASIDE') aside = true;
    }
    return legal ? 'legal' : footer ? 'footer' : header ? 'header' : aside ? 'aside' : 'main';
  };

  const clippedText = (el, rect) => {
    let clips = false;
    for (let a = el; a && a !== document.documentElement; a = a.parentElement) {
      const s = styleOf(a);
      if (s.overflowX === 'visible' && s.overflowY === 'visible') continue;
      clips = true;
      if (a !== el) {
        const r = a.getBoundingClientRect();
        if (rect.right > r.right + 1 || rect.bottom > r.bottom + 1 || rect.left < r.left - 1 || rect.top < r.top - 1) return true;
      }
    }
    return clips && (el.scrollWidth > el.clientWidth + 1 || el.scrollHeight > el.clientHeight + 1);
  };

  const blocks = new Map();
  let truncated = false;
  const walker = document.createTreeWalker(document.body || document.documentElement, NodeFilter.SHOW_TEXT);
  for (let node = walker.nextNode(); node; node = walker.nextNode()) {
    const parent = node.parentElement;
    if (!parent || parent.closest(SKIP) || !node.nodeValue.trim()) continue;
    let block = parent;
    while (block.parentElement && !isBlockLevel(block)) block = block.parentElement;
    let entry = blocks.get(block);
    if (!entry) {
      if (blocks.size >= opts.maxBlocks) { truncated = true; break; }
      entry = { from: parent, text: '' };
      blocks.set(block, entry);
    }
    if (entry.text.length <= opts.maxText) entry.text += node.nodeValue;
  }

  const out = [];
  for (const [el, entry] of blocks) {
    const rect = el.getBoundingClientRect();
    const s = styleOf(el);
    const closed = inClosedDetails(el);
    const visible = !closed && isVisible(el, rect);
    const bg = backgroundOf(el);
    const fg = parseColor(s.color);
    const weight = s.fontWeight === 'bold' ? 700 : s.fontWeight === 'normal' ? 400 : Math.round(parseFloat(s.fontWeight));
    const x = rect.left + window.scrollX, y = rect.top + window.scrollY;
    out.push({
      text: entry.text,
      tag: el.tagName.toLowerCase(),
      font_size_px: parseFloat(s.fontSize),
      font_weight: weight,
      color: fg && bg ? hex(fg.a < 1 ? over(fg, bg) : fg) : (fg && fg.a === 1 ? hex(fg) : null),
      background_color: bg ? hex(bg) : null,
      bbox: [x, y, rect.width, rect.height],
      visible,
      in_viewport_on_load: visible && y >= 0 && y + rect.height <= viewportHeight,
      requires_interaction: closed || (!visible && controlledByCollapsed(el)),
      region: regionOf(entry.from),
      overflow_clipped: clippedText(el, rect),
    });
  }
  return { blocks: out, truncated };
}
"""


def clean_text(text: str) -> str:
    """No NUL or lone surrogate (neither survives PostgreSQL or JSON), whitespace runs collapsed to one space."""
    return " ".join(_UNWANTED.sub("", text).split())


def _number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, int | float) or not math.isfinite(value):
        return None
    return float(value)


def _flag(value: object) -> bool | None:
    return value if isinstance(value, bool) else None


def sanitize_block(raw: object, viewport: str) -> tuple[dict | None, bool]:
    """The block in the contract's shape (None when it holds no usable text), and whether its text was cut."""
    if not isinstance(raw, dict) or not isinstance(raw.get("text"), str):
        return None, False
    text = clean_text(raw["text"])
    if not text:
        return None, False
    cut = len(text) > MAX_TEXT_CHARS
    size = _number(raw.get("font_size_px"))
    weight = _number(raw.get("font_weight"))
    bbox = raw.get("bbox")
    numbers = [_number(v) for v in bbox] if isinstance(bbox, list) and len(bbox) == 4 else None
    color, background = raw.get("color"), raw.get("background_color")
    region = raw.get("region")
    tag = raw.get("tag")
    return {
        "viewport": viewport,
        "text": text[:MAX_TEXT_CHARS],
        "tag": tag.lower()[:30] if isinstance(tag, str) and tag else None,
        "font_size_px": max(0.0, size) if size is not None else 0.0,
        "font_weight": min(1000, max(100, round(weight))) if weight is not None else None,
        "color": color if isinstance(color, str) and _COLOR.fullmatch(color) else None,
        "background_color": background if isinstance(background, str) and _COLOR.fullmatch(background) else None,
        "bbox": [round(v, 2) for v in numbers] if numbers and None not in numbers else None,
        "visible": raw.get("visible") is True,
        "in_viewport_on_load": _flag(raw.get("in_viewport_on_load")),
        "requires_interaction": _flag(raw.get("requires_interaction")),
        "region": region if region in REGIONS else "main",  # never null: R6 cannot pass a block of unknown region
        "overflow_clipped": _flag(raw.get("overflow_clipped")),
    }, cut


@dataclass(frozen=True)
class Measured:
    blocks: tuple[dict, ...]
    truncated: bool


async def measure_blocks(session, viewport: str, max_blocks: int) -> Measured:
    """Measure the page the CDP `session` is attached to. Raises whatever the protocol raises on a dead page."""
    tree = await session.send("Page.getFrameTree")
    world = await session.send("Page.createIsolatedWorld", {"frameId": tree["frameTree"]["frame"]["id"], "worldName": WORLD_NAME})
    options = {"words": list(PLACEMENT_WORDS), "maxBlocks": max_blocks, "maxText": MAX_TEXT_CHARS}
    reply = await session.send(
        "Runtime.evaluate",
        {
            "expression": f"({MEASURE_SCRIPT})({_json(options)})",
            "contextId": world["executionContextId"],
            "returnByValue": True,
        },
    )
    value = reply.get("result", {}).get("value") if "exceptionDetails" not in reply else None
    if not isinstance(value, dict) or not isinstance(value.get("blocks"), list):
        return Measured((), False)
    truncated = value.get("truncated") is True or len(value["blocks"]) > max_blocks
    blocks = []
    for raw in value["blocks"][:max_blocks]:
        block, cut = sanitize_block(raw, viewport)
        truncated = truncated or cut
        if block is not None:
            blocks.append(block)
    return Measured(tuple(blocks), truncated)


def _json(value: object) -> str:
    import json

    return json.dumps(value)

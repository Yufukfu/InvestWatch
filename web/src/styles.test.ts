/// <reference types="node" />
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

// The visual contract of web-design-system: tokens declared once, measured contrast, fonts from our
// own origin, nothing inline in the served HTML. Values are read from the real files, not copied.
const webRoot = resolve(import.meta.dirname, '..');
const css = readFileSync(resolve(webRoot, 'src/styles.css'), 'utf8');
const html = readFileSync(resolve(webRoot, 'index.html'), 'utf8');
const mainSource = readFileSync(resolve(webRoot, 'src/main.tsx'), 'utf8');

const rootBlock = /:root\s*\{([^}]*)\}/.exec(css)?.[1] ?? '';
const tokens = new Map<string, string>();
for (const [, name, value] of rootBlock.matchAll(/(--[\w-]+)\s*:\s*([^;]+);/g)) tokens.set(name, value.trim());

function channel(hex: string, start: number): number {
  const v = parseInt(hex.slice(start, start + 2), 16) / 255;
  return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4;
}

function luminance(name: string): number {
  const hex = tokens.get(name);
  if (!hex || !/^#[0-9a-f]{6}$/i.test(hex)) throw new Error(`token ${name} is not a 6-digit hex colour: ${hex}`);
  return 0.2126 * channel(hex, 1) + 0.7152 * channel(hex, 3) + 0.0722 * channel(hex, 5);
}

function contrast(fg: string, bg: string): number {
  const [a, b] = [luminance(fg), luminance(bg)].sort((x, y) => y - x);
  return (a + 0.05) / (b + 0.05);
}

// [text token, background token]: every text-on-fill pair the stylesheet uses.
const TEXT_PAIRS: Array<[string, string]> = [
  ['--text', '--surface'],
  ['--text', '--bg'],
  ['--text', '--surface-2'],
  ['--text', '--tint-selected'],
  ['--text', '--accent-tint'],
  ['--text', '--tint-high'],
  ['--muted', '--tint-high'],
  ['--accent', '--tint-high'],
  ['--accent', '--tint-selected'],
  ['--muted', '--tint-selected'],
  ['--accent', '--tint-hover'],
  ['--muted', '--tint-hover'],
  ['--muted', '--surface'],
  ['--muted', '--bg'],
  ['--muted', '--surface-2'],
  ['--placeholder', '--surface'],
  ['--accent', '--surface'],
  ['--link', '--surface'],
  ['--link', '--tint-high'],
  ['--risk-high-fg', '--tint-high'],
  ['--accent', '--surface-2'],
  ['--accent-text', '--accent'],
  ['--accent-text', '--accent-strong'],
  ['--accent-text', '--amber'],
  ['--accent-text', '--risk-high'],
  ['--green', '--surface'],
  ['--m3', '--surface'],
  ['--risk-high-fg', '--risk-high-bg'],
  ['--risk-medium-fg', '--risk-medium-bg'],
  ['--risk-low-fg', '--risk-low-bg'],
  ['--risk-none-fg', '--risk-none-bg'],
  ['--badge-degraded-fg', '--badge-degraded-bg'],
  ['--badge-down-fg', '--badge-down-bg'],
  ['--risk-high-fg', '--surface'],
  ['--risk-high', '--surface'],
  ['--green-text', '--surface'],
  ['--text-2', '--surface'],
  ['--text-2', '--tint-hover'],
  ['--text', '--tint-hover'],
  ['--green-text', '--tint-hover'],
  ['--accent-text', '--link'],
  ['--accent-text', '--link-strong'],
  ['--accent-text', '--toast-bg'],
  ['--toast-meta', '--toast-bg'],
  ['--toast-ghost', '--toast-bg'],
  ['--toast-bg', '--accent-text'],
  ['--toast-bg', '--toast-ghost'],
  ['--callout-text', '--callout-bg'],
  ['--link', '--callout-bg'],
  ['--amber', '--surface'],
  ['--accent', '--border'],
  ['--text', '--callout-bg'],
  ['--banner-fg', '--banner-bg'],
  ['--link', '--banner-bg'],
  ['--link-strong', '--surface'],
  ['--link-strong', '--banner-bg'],
  ['--link-strong', '--tint-hover'],
];

// Non-text parts (control borders, focus ring, slider) need 3:1.
const NON_TEXT_PAIRS: Array<[string, string]> = [
  ['--control-border', '--surface'],
  ['--control-border', '--surface-2'],
  ['--focus', '--surface'],
  ['--focus', '--bg'],
  ['--accent', '--surface'],
  ['--toast-line', '--toast-bg'],
  ['--risk-high', '--toast-bg'],
  ['--accent-text', '--toast-bg'],
];

describe('design tokens', () => {
  it.each(TEXT_PAIRS)('text %s on %s is at least 4.5:1', (fg, bg) => {
    expect(contrast(fg, bg)).toBeGreaterThanOrEqual(4.5);
  });

  it.each(NON_TEXT_PAIRS)('control %s against %s is at least 3:1', (fg, bg) => {
    expect(contrast(fg, bg)).toBeGreaterThanOrEqual(3);
  });

  it('keeps the module colour out of the risk colours', () => {
    expect(tokens.get('--m3')).toBeDefined();
    for (const risk of ['--risk-high', '--risk-high-fg', '--amber', '--green']) {
      expect(tokens.get('--m3')).not.toBe(tokens.get(risk));
    }
  });

  it('declares every hex colour once, in :root, so no section owns a colour', () => {
    const outside = css.replace(/:root\s*\{[^}]*\}/, '');
    expect(outside.match(/#[0-9a-fA-F]{3,8}\b/g) ?? []).toEqual([]);
  });

  it('draws the focus ring at least 2px wide', () => {
    const width = /:focus-visible\s*\{\s*outline:\s*(\d+)px/.exec(css)?.[1];
    expect(Number(width)).toBeGreaterThanOrEqual(2);
  });

  it('turns animation off for reduced motion', () => {
    expect(css).toMatch(/@media \(prefers-reduced-motion: reduce\)[^]*animation: none/);
  });

  it('uses no text smaller than 12px', () => {
    const sizes = [...css.matchAll(/font-size:\s*(\d+(?:\.\d+)?)px/g)].map((m) => Number(m[1]));
    expect(sizes.filter((s) => s < 12)).toEqual([]);
  });
});

// Every `selectors { body }` pair, media blocks flattened (the stylesheet never nests rules).
const rules = [...css.matchAll(/([^{}]+)\{([^{}]*)\}/g)].map(([, sel, body]) => ({
  selectors: sel.replace(/\/\*[^]*?\*\//g, '').split(',').map((s) => s.trim()),
  body,
}));

function px(value: string): number {
  const resolved = value.trim().replace(/var\((--[\w-]+)\)/g, (_, n: string) => tokens.get(n) ?? 'NaN');
  const m = /^(-?\d+(?:\.\d+)?)px$/.exec(resolved);
  if (!m) throw new Error(`not a px value: ${value}`);
  return Number(m[1]);
}

// Value of `prop` in the last rule that lists exactly `selector`.
function declared(selector: string, prop: string): string | undefined {
  const values = rules
    .filter((r) => r.selectors.includes(selector))
    .map((r) => new RegExp(`(?:^|[;\\s])${prop}\\s*:\\s*([^;]+)`).exec(r.body)?.[1]?.trim())
    .filter(Boolean);
  return values.at(-1);
}

describe('interaction styling', () => {
  it('underlines nothing at rest: only :hover or :focus-visible rules may set an underline', () => {
    const resting = rules.filter((r) => /text-decoration(-line)?\s*:[^;]*underline/.test(r.body))
      .flatMap((r) => r.selectors).filter((s) => !/:(hover|focus-visible)/.test(s));
    expect(resting).toEqual([]);
  });

  it('removes the browser underline from every link in one base rule', () => {
    expect(declared('a', 'text-decoration')).toBe('none');
  });

  it('keeps text links distinguishable by weight, not only colour', () => {
    expect(Number(declared('a', 'font-weight'))).toBeGreaterThanOrEqual(500);
  });

  it('leaves at least 16px above the data-table disclosure', () => {
    const top = declared('.trend-table', 'margin-top') ?? declared('.trend-table', 'margin')?.split(/\s+/)[0];
    expect(px(top ?? '0px')).toBeGreaterThanOrEqual(16);
  });

  it('keeps the data-table button on the right whether the table is open or closed', () => {
    expect(declared('.trend-table summary', 'margin-left')).toBe('auto');
    expect(declared('.trend-table summary', 'width')).toBe('fit-content');
  });

  it('draws the same inset arrow on every select, not only the filter ones', () => {
    expect(declared('select', 'appearance')).toBe('none');
    expect(px(declared('select', 'padding-right') ?? '0px')).toBeGreaterThanOrEqual(36);
  });

  it('uses the soft border on labelled controls and the 3:1 border on text fields at rest', () => {
    expect(tokens.get('--field-border')).toBeDefined();
    expect(contrast('--field-border', '--surface')).toBeLessThan(contrast('--control-border', '--surface'));
    const rest = (sel: string) => declared(sel, 'border') ?? declared(sel, 'border-color') ?? '';
    for (const sel of ['.btn', '.chip', '.filter-chip', '.trend-buckets', '.trend-table summary', '.segmented button', '.nav-toggle']) {
      expect(rest(sel), sel).toContain('var(--field-border)');
    }
    for (const sel of ['input', 'select', 'textarea', '.field input', '.field select', '.status-editor textarea']) {
      expect(rest(sel), sel).toContain('var(--control-border)');
    }
    expect(declared('input:focus-visible', 'border-color')).toBe('var(--control-border)');
  });

  it('keeps a disabled pager button as opaque as an enabled one', () => {
    expect(declared('.pager .btn:disabled', 'opacity')).toBe('1');
  });

  it('gives every control a 120-150ms transition from tokens', () => {
    const dur = Number(/^(\d+)ms$/.exec(tokens.get('--dur') ?? '')?.[1]);
    expect(dur).toBeGreaterThanOrEqual(120);
    expect(dur).toBeLessThanOrEqual(150);
    for (const sel of ['.btn', '.chip', '.filter-chip', 'input', 'select', 'textarea', 'button.link', '.trend-table summary', '.segmented button', '.trend-buckets button', '.app-nav a', '.sort', '.rule-group summary', '.shortcuts summary']) {
      expect(declared(sel, 'transition'), sel).toContain('var(--dur)');
    }
  });

  it('draws control corners from radius tokens, never a literal', () => {
    for (const sel of ['.btn', '.chip', '.filter-chip', 'input', '.trend-table summary', '.segmented button', '.nav-toggle']) {
      expect(declared(sel, 'border-radius'), sel).toMatch(/^var\(--radius/);
    }
  });

  it('shows hover and active feedback on buttons', () => {
    expect(rules.some((r) => r.selectors.some((s) => s.startsWith('.btn:active')))).toBe(true);
    expect(rules.some((r) => r.selectors.some((s) => s.startsWith('.chip:hover') || s.startsWith('.chip:has(input:not(:checked)):hover')))).toBe(true);
  });

  it('raises surfaces with a token shadow, not ad-hoc ones', () => {
    for (const sel of ['.detail', '.toast']) expect(declared(sel, 'box-shadow'), sel).toMatch(/var\(--shadow/);
  });
});

describe('served HTML and fonts', () => {
  it('has no style attribute and no inline style block in index.html', () => {
    expect(html).not.toMatch(/\sstyle\s*=/i);
    expect(html).not.toMatch(/<style[\s>]/i);
  });

  it('imports only latin and latin-ext font files from fontsource, for all three families', () => {
    const fontImports = [...mainSource.matchAll(/import\s+'(@fontsource[^']+)'/g)].map((m) => m[1]);
    expect(fontImports.length).toBeGreaterThan(0);
    for (const path of fontImports) {
      expect(path, path).toMatch(/\/latin(-ext)?(-\d+)?\.css$/);
    }
    for (const family of ['space-grotesk', 'inter', 'geist-mono']) {
      const own = fontImports.filter((p) => p.includes(`/${family}/`));
      expect(own.some((p) => /\/latin(-\d+)?\.css$/.test(p)), `${family} latin`).toBe(true);
      expect(own.some((p) => /\/latin-ext(-\d+)?\.css$/.test(p)), `${family} latin-ext`).toBe(true);
    }
  });

  it('imports latin-ext for every weight it imports latin for, so Polish letters never fall back', () => {
    const fontImports = [...mainSource.matchAll(/import\s+'(@fontsource[^']+)'/g)].map((m) => m[1]);
    const weights = (subset: RegExp, family: string) =>
      fontImports
        .filter((p) => p.includes(`/${family}/`))
        .map((p) => subset.exec(p)?.[1])
        .filter(Boolean)
        .sort();
    for (const family of ['space-grotesk', 'inter', 'geist-mono']) {
      expect(weights(/\/latin-(\d+)\.css$/, family), family).toEqual(weights(/\/latin-ext-(\d+)\.css$/, family));
    }
  });

  it('sets the three families as font stacks with a system fallback', () => {
    expect(css).toMatch(/--font-text:[^;]*Inter[^;]*sans-serif/);
    expect(css).toMatch(/--font-display:[^;]*Space Grotesk[^;]*sans-serif/);
    expect(css).toMatch(/--font-mono:[^;]*Geist Mono[^;]*monospace/);
  });
});

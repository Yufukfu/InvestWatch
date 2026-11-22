import { render, screen, within } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import type { FindingDetail, FindingRow, RuleView } from '../model';
import { FindingDetailPanel } from './FindingDetailPanel';
import { FindingsTable } from './FindingsTable';

// Model output and scraped quotes are untrusted (issue #54): markup, Markdown links,
// bare URLs and bidi controls must stay inert text, and a right-to-left override must
// stay inside the element that holds the value.
const IMG = '<img src=x onerror=alert(1)>';
const MD = '[link](javascript:alert(1))';
const URL_TEXT = 'https://evil.example/x';
const RLO = '‮';
const hostile = (label: string) => `${label} ${IMG} ${MD} ${URL_TEXT} ${RLO}gpj.exe`;

const evidence = hostile('cytat');
const explanation = hostile('wyjaśnienie');
const passedExplanation = hostile('spełniona');
const summary = hostile('podsumowanie');
const title = hostile('tytuł');
const name = hostile('nadawca');
const handle = hostile('@uchwyt');

const rule = (over: Partial<RuleView> = {}): RuleView => ({
  ruleId: 'R3',
  name: 'Informacja o ryzyku',
  result: 'fail',
  severity: 'high',
  evidence,
  explanation,
  legalBasis: 'art. 44 ust. 2 lit. b',
  method: 'llm',
  ...over,
});

const detail = (over: Partial<FindingDetail> = {}): FindingDetail => ({
  id: 'f1',
  documentId: 'doc-1',
  module: 'M2',
  title,
  summary,
  score: 0.86,
  riskLevel: 'high',
  status: 'new',
  note: null,
  url: 'https://alfa.example.com/konto',
  platform: 'web',
  detectedAt: '2026-11-21T15:00:00Z',
  advertiser: { name, handle, profileUrl: 'https://instagram.com/uchwyt', inRegistry: false },
  rules: [rule(), rule({ ruleId: 'R1', result: 'pass', severity: 'low', evidence: null, explanation: passedExplanation })],
  ...over,
});

const base = { isLoading: false, isError: false, notFound: false, onClose: vi.fn() };

// Every text node holding U+202E must sit directly in a dir="auto" element whose whole text is
// one of the untrusted values: then no UI text shares the bidi isolate with the override.
function expectOverridesIsolated(root: HTMLElement, values: string[]) {
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  let found = 0;
  for (let n = walker.nextNode(); n; n = walker.nextNode()) {
    if (!n.nodeValue?.includes(RLO)) continue;
    found++;
    const el = n.parentElement!;
    expect(el).toHaveAttribute('dir', 'auto');
    expect(values).toContain(el.textContent);
  }
  return found;
}

describe('untrusted finding text', () => {
  it('shows markup, Markdown links and bare URLs in every detail field as inert text', () => {
    const { container } = render(<FindingDetailPanel {...base} detail={detail()} />);
    const panel = screen.getByRole('dialog');

    expect(container.querySelector('img')).toBeNull();
    expect(container.querySelector('[onerror]')).toBeNull();
    for (const value of [evidence, explanation, passedExplanation, summary, title, name, handle]) {
      expect(panel.textContent).toContain(value);
    }
    expect(within(panel).queryByRole('link', { name: 'link' })).toBeNull();
    const hrefs = within(panel)
      .getAllByRole('link')
      .map((a) => a.getAttribute('href'));
    expect(hrefs).toEqual(['https://alfa.example.com/konto', 'https://instagram.com/uchwyt']);
    expect(hrefs.join(' ')).not.toMatch(/javascript:|evil\.example/);
  });

  it('keeps each right-to-left override inside a dir="auto" element holding only that value', () => {
    render(<FindingDetailPanel {...base} detail={detail()} />);
    const panel = screen.getByRole('dialog');
    const values = [evidence, explanation, passedExplanation, summary, title, name, handle];

    // title, summary, explanation, evidence, collapsed explanation, name, handle
    expect(expectOverridesIsolated(panel, values)).toBe(7);

    const quote = panel.querySelector('blockquote')!;
    const ev = within(quote).getByText(evidence);
    expect(ev).toHaveAttribute('dir', 'auto');
    expect(quote.textContent!.endsWith('”')).toBe(true);
    expect(ev.textContent!.endsWith('”')).toBe(false);

    const collapsed = within(panel).getByText(passedExplanation);
    expect(collapsed.parentElement!.textContent).toBe(` – ${passedExplanation}`);
  });

  it('isolates the excerpt and full text too', () => {
    const text = hostile('treść');
    const excerpt = hostile('fragment');
    render(<FindingDetailPanel {...base} detail={detail({ rules: [], summary: null, advertiser: undefined, title: 'Bez', excerpt, documentText: text })} />);
    expect(expectOverridesIsolated(screen.getByRole('dialog'), [excerpt, text])).toBe(2);
  });

  it('isolates the handle when it is not a link', () => {
    render(<FindingDetailPanel {...base} detail={detail({ advertiser: { name: null, handle, profileUrl: 'javascript:alert(1)' } })} />);
    const panel = screen.getByRole('dialog');
    expect(within(panel).getByText(handle).tagName).not.toBe('A');
    expect(within(panel).getByText(handle)).toHaveAttribute('dir', 'auto');
  });

  it('isolates the title in the findings table', () => {
    const row: FindingRow = {
      id: '1',
      module: 'M2',
      title,
      platform: 'web',
      score: 0.5,
      riskLevel: 'high',
      status: 'new',
      detectedAt: '2026-11-21T15:00:00Z',
      documentId: 'doc-1',
      url: 'https://example.com/post/1',
    };
    const { container } = render(
      <FindingsTable
        rows={[row]}
        total={1}
        onFirstPage={vi.fn()}
        sort="-detected_at"
        onSort={vi.fn()}
        onSelect={vi.fn()}
        onReset={vi.fn()}
        selectedId={undefined}
        isLoading={false}
        isFetching={false}
        isError={false}
      />,
    );
    expect(container.querySelector('img')).toBeNull();
    expect(screen.queryByRole('link')).toBeNull();
    expect(expectOverridesIsolated(container, [title])).toBe(1);
    expect(screen.getByText(title).tagName).toBe('BUTTON');
  });
});

import { fireEvent, render, screen, within } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import type { FindingDetail, RuleView } from '../model';
import { FindingDetailPanel } from './FindingDetailPanel';

const rule = (over: Partial<RuleView> = {}): RuleView => ({
  ruleId: 'R3',
  name: 'Informacja o ryzyku',
  result: 'fail',
  severity: 'high',
  evidence: 'Zarabiaj nawet do 18% rocznie',
  explanation: 'Brak ostrzeżenia o ryzyku.',
  legalBasis: 'art. 44 ust. 2 lit. b',
  method: 'hybrid',
  ...over,
});

const detail = (over: Partial<FindingDetail> = {}): FindingDetail => ({
  id: 'f1',
  documentId: 'doc-1',
  module: 'M2',
  title: 'Obietnica 18% zysku',
  summary: 'Materiał eksponuje stopę zwrotu.',
  score: 0.86,
  riskLevel: 'high',
  status: 'new',
  note: null,
  url: 'https://alfa.example.com/konto',
  platform: 'web',
  detectedAt: '2026-11-21T15:00:00Z',
  firm: { name: 'Alfa DM S.A.', authorized: true, registryType: 'brokerage_house', matchConfidence: 0.95 },
  advertiser: undefined,
  rules: [
    rule(),
    rule({ ruleId: 'R12a', name: 'Porównania', result: 'uncertain', severity: 'medium', legalBasis: 'art. 44 ust. 3', explanation: 'Niejasne porównanie.' }),
    rule({ ruleId: 'R1', name: 'Identyfikacja firmy', result: 'pass', severity: 'medium', explanation: 'Nazwa firmy jest podana.' }),
    rule({ ruleId: 'R10', name: 'Waluta', result: 'pass', severity: 'low' }),
    rule({ ruleId: 'R9', name: 'Symulacje', result: 'not_applicable', severity: 'low' }),
  ],
  excerpt: 'Konto Premium Alfa Inwestycje.',
  documentText: 'Pełny tekst strony.',
  screenshotUrl: '/api/documents/d1/screenshot/desktop',
  pipelineVersion: '0.1.0-mock',
  llm: 'gemma3:4b',
  ...over,
});

const base = { isLoading: false, isError: false, notFound: false, onClose: vi.fn() };

describe('FindingDetailPanel', () => {
  it('shows every fail and uncertain rule with legal basis and explanation, without any expand', () => {
    render(<FindingDetailPanel {...base} detail={detail()} />);
    const issues = screen.getByRole('region', { name: /Naruszenia/ });
    const items = within(issues).getAllByRole('listitem');
    expect(items).toHaveLength(2);
    expect(items[0]).toHaveTextContent('R3');
    expect(items[0]).toHaveTextContent('Informacja o ryzyku');
    expect(items[0]).toHaveTextContent('art. 44 ust. 2 lit. b');
    expect(items[0]).toHaveTextContent('Brak ostrzeżenia o ryzyku.');
    expect(items[0]).toHaveTextContent('Zarabiaj nawet do 18% rocznie');
    expect(items[0]).toHaveTextContent('Waga: wysoka');
    expect(items[1]).toHaveTextContent('R12a');
    expect(items[1]).toHaveTextContent('Niepewne');
    for (const el of [items[0], items[1]]) expect(el.closest('details')).toBeNull();
  });

  it('collapses passing rules with their count, and not applicable ones apart', () => {
    render(<FindingDetailPanel {...base} detail={detail()} />);
    const passed = screen.getByText('Spełnione (2)').closest('details')!;
    expect(passed).not.toHaveAttribute('open');
    expect(within(passed).getByText(/Identyfikacja firmy/)).toBeInTheDocument();
    expect(screen.getByText('Nie dotyczy (1)')).toBeInTheDocument();
  });

  it('orders issues by severity, high first', () => {
    const rules = [rule({ ruleId: 'R8', severity: 'low' }), rule({ ruleId: 'R6', severity: 'high' }), rule({ ruleId: 'R5', severity: 'medium' })];
    render(<FindingDetailPanel {...base} detail={detail({ rules })} />);
    const items = within(screen.getByRole('region', { name: /Naruszenia/ })).getAllByRole('listitem');
    expect(items.map((i) => i.querySelector('.rule-id')?.textContent)).toEqual(['R6', 'R5', 'R8']);
  });

  it('tags each result with its own word, so greyscale tells them apart: Naruszenie, Niepewne, Zgodne', () => {
    for (const module of ['M1', 'M2'] as const) {
      const { unmount } = render(<FindingDetailPanel {...base} detail={detail({ module })} />);
      const items = within(screen.getByRole('region', { name: /Naruszenia|Sygnały/ })).getAllByRole('listitem');
      expect(items[0]).toHaveTextContent('Naruszenie');
      expect(items[0]).not.toHaveTextContent('Niepewne');
      expect(items[1]).toHaveTextContent('Niepewne');
      expect(items[1]).not.toHaveTextContent('Naruszenie');
      const passed = screen.getByText('Spełnione (2)').closest('details')!;
      expect(within(passed).getAllByText('Zgodne')).toHaveLength(2);
      unmount();
    }
  });

  it('titles M1/M3 findings Sygnały ryzyka', () => {
    render(<FindingDetailPanel {...base} detail={detail({ module: 'M1', rules: [rule({ ruleId: 'S1.2', name: 'Kod polecający' })] })} />);
    const item = within(screen.getByRole('region', { name: 'Sygnały ryzyka (1)' })).getByRole('listitem');
    expect(item).toHaveTextContent('S1.2');
  });

  it('shows the risk and module as a tag line above the title, and the score, platform, time and status in the strip', () => {
    render(<FindingDetailPanel {...base} detail={detail({ module: 'M1' })} />);
    const tag = screen.getByText('M1 · Finfluencerzy');
    expect(tag.parentElement).toHaveTextContent('Wysoki');
    expect(tag.parentElement?.nextElementSibling).toHaveTextContent('Obietnica 18% zysku');
    const strip = screen.getByLabelText('Dane zgłoszenia');
    expect(within(strip).getByText('0,86')).toBeInTheDocument();
    expect(within(strip).getByText('Strona WWW')).toBeInTheDocument();
    expect(within(strip).getByText('21.11.2026 · 15:00 UTC')).toBeInTheDocument();
    expect(within(strip).getByText('Nowe')).toBeInTheDocument();
    expect(within(strip).getByRole('link', { name: /Otwórz źródło/ })).toHaveAttribute('href', 'https://alfa.example.com/konto');
  });

  it('labels the source and marks only a high-risk score for the red figure', () => {
    const { rerender } = render(<FindingDetailPanel {...base} detail={detail()} />);
    const strip = screen.getByLabelText('Dane zgłoszenia');
    expect(within(strip).getByText('Źródło')).toBeInTheDocument();
    expect(within(strip).getByText('0,86')).toHaveClass('score-high');
    rerender(<FindingDetailPanel {...base} detail={detail({ riskLevel: 'medium' })} />);
    expect(within(strip).getByText('0,86')).not.toHaveClass('score-high');
  });

  it('puts the firm and the advertiser in two labelled blocks', () => {
    render(
      <FindingDetailPanel
        {...base}
        detail={detail({ advertiser: { name: 'Jan', handle: '@jan', profileUrl: undefined, inRegistry: false, onWarningList: false } })}
      />,
    );
    expect(within(screen.getByRole('group', { name: 'Firma inwestycyjna' })).getByText('Alfa DM S.A.')).toBeInTheDocument();
    expect(within(screen.getByRole('group', { name: 'Podmiot reklamujący' })).getByText('@jan')).toBeInTheDocument();
  });

  it('says so when no rule failed', () => {
    render(<FindingDetailPanel {...base} detail={detail({ rules: [rule({ result: 'pass' })] })} />);
    expect(screen.getByText('Brak naruszeń ani niepewnych wyników.')).toBeInTheDocument();
  });

  it('shows header, summary, firm and source link', () => {
    render(<FindingDetailPanel {...base} detail={detail()} />);
    expect(screen.getByRole('heading', { level: 2, name: 'Obietnica 18% zysku' })).toBeInTheDocument();
    expect(screen.getByText('Wysoki')).toBeInTheDocument();
    expect(screen.getByText('Materiał eksponuje stopę zwrotu.')).toBeInTheDocument();
    expect(screen.getByText('Alfa DM S.A.')).toBeInTheDocument();
    expect(screen.getByText('Firma w rejestrze KNF')).toBeInTheDocument();
    const link = screen.getByRole('link', { name: /Otwórz źródło/ });
    expect(link).toHaveAttribute('href', 'https://alfa.example.com/konto');
    expect(link).toHaveAttribute('rel', 'noopener noreferrer');
    expect(screen.getByText(/gemma3:4b/)).toBeInTheDocument();
  });

  it('shows the re-scan badge for a changed page and none without a re-scan state', () => {
    const { unmount } = render(<FindingDetailPanel {...base} detail={detail({ rescan: { state: 'removed' } })} />);
    expect(screen.getByText('Usunięta')).toBeInTheDocument();
    unmount();
    render(<FindingDetailPanel {...base} detail={detail()} />);
    expect(screen.queryByText('Usunięta')).toBeNull();
    expect(screen.queryByText('Zmieniona')).toBeNull();
  });

  it('flags an unauthorised firm and an advertiser on the warning list', () => {
    render(
      <FindingDetailPanel
        {...base}
        detail={detail({
          firm: { name: 'Krzak Ltd', authorized: false },
          advertiser: { name: 'Jan', handle: '@inwestor_jan', profileUrl: 'https://instagram.com/inwestor_jan', inRegistry: false, onWarningList: true },
        })}
      />,
    );
    expect(screen.getByText('Firma spoza rejestru KNF')).toBeInTheDocument();
    expect(screen.getByText('@inwestor_jan')).toBeInTheDocument();
    expect(screen.getByText('Na liście ostrzeżeń KNF')).toBeInTheDocument();
  });

  it('does not link a non-http source url', () => {
    render(<FindingDetailPanel {...base} detail={detail({ url: 'javascript:alert(1)' })} />);
    expect(screen.queryByRole('link', { name: /Otwórz źródło/ })).toBeNull();
    expect(screen.getByText('javascript:alert(1)')).toBeInTheDocument();
  });

  it('renders scraped markup as text', () => {
    const { container } = render(<FindingDetailPanel {...base} detail={detail({ excerpt: '<script>x()</script><b>b</b>' })} />);
    expect(screen.getByText('<script>x()</script><b>b</b>')).toBeInTheDocument();
    expect(container.querySelector('script, b')).toBeNull();
  });

  it('shows the screenshot and a message when it fails to load', () => {
    render(<FindingDetailPanel {...base} detail={detail()} />);
    const img = screen.getByRole('img', { name: 'Zrzut ekranu materiału (desktop)' });
    expect(img).toHaveAttribute('src', '/api/documents/d1/screenshot/desktop');
    fireEvent.error(img);
    expect(screen.getByText('Nie udało się wczytać zrzutu ekranu.')).toBeInTheDocument();
    expect(screen.getByRole('heading', { level: 2 })).toBeInTheDocument();
  });

  it('shows no screenshot for a url outside the api', () => {
    render(<FindingDetailPanel {...base} detail={detail({ screenshotUrl: 'https://evil.example/x.png' })} />);
    expect(screen.queryByRole('img', { name: /Zrzut ekranu/ })).toBeNull();
  });

  it('shows the not-found and error states with a close action', () => {
    const onClose = vi.fn();
    const { rerender } = render(<FindingDetailPanel {...base} onClose={onClose} detail={undefined} isError notFound />);
    expect(screen.getByRole('alert')).toHaveTextContent('To zgłoszenie nie istnieje.');
    fireEvent.click(screen.getByRole('button', { name: 'Zamknij' }));
    expect(onClose).toHaveBeenCalled();
    rerender(<FindingDetailPanel {...base} onClose={onClose} detail={undefined} isError />);
    expect(screen.getByRole('alert')).toHaveTextContent('Nie udało się pobrać szczegółów zgłoszenia.');
    rerender(<FindingDetailPanel {...base} onClose={onClose} detail={undefined} isLoading />);
    expect(screen.getByText('Ładowanie szczegółów…')).toBeInTheDocument();
  });

  it('focuses the close button, closes on Escape and returns focus', () => {
    const onClose = vi.fn();
    const opener = document.createElement('button');
    document.body.appendChild(opener);
    opener.focus();
    const { unmount } = render(<FindingDetailPanel {...base} onClose={onClose} detail={detail()} />);
    expect(screen.getByRole('button', { name: 'Zamknij' })).toHaveFocus();
    fireEvent.keyDown(screen.getByRole('dialog'), { key: 'Escape' });
    expect(onClose).toHaveBeenCalledTimes(1);
    unmount();
    expect(opener).toHaveFocus();
    opener.remove();
  });

  it('closes on Escape when focus is outside the panel', () => {
    const onClose = vi.fn();
    render(<FindingDetailPanel {...base} onClose={onClose} detail={detail()} />);
    (document.activeElement as HTMLElement).blur();
    fireEvent.keyDown(document.body, { key: 'Escape' });
    expect(onClose).toHaveBeenCalledTimes(1);
    fireEvent.keyDown(document.body, { key: 'Enter' });
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('keeps Tab inside the panel (modal)', () => {
    render(<FindingDetailPanel {...base} detail={detail()} />);
    const dialog = screen.getByRole('dialog');
    expect(dialog).toHaveAttribute('aria-modal', 'true');
    const close = screen.getByRole('button', { name: 'Zamknij' });
    const all = dialog.querySelectorAll<HTMLElement>('a[href], button, summary');
    const last = all[all.length - 1];
    expect(last).not.toBe(close);
    last.focus();
    fireEvent.keyDown(last, { key: 'Tab' });
    expect(close).toHaveFocus();
    fireEvent.keyDown(close, { key: 'Tab', shiftKey: true });
    expect(last).toHaveFocus();
    // Tab in the middle is left to the browser.
    const middle = screen.getByRole('link', { name: /Otwórz źródło/ });
    middle.focus();
    fireEvent.keyDown(middle, { key: 'Tab' });
    expect(middle).toHaveFocus();
  });

  it('Escape in a field that holds text moves focus to Zamknij first, the next Escape closes', () => {
    const onClose = vi.fn();
    render(<FindingDetailPanel {...base} onClose={onClose} detail={detail()} statusEditor={<textarea aria-label="n" defaultValue="" />} />);
    const box = screen.getByLabelText('n') as HTMLTextAreaElement;
    fireEvent.change(box, { target: { value: 'niezapisana notatka' } });
    box.focus();
    fireEvent.keyDown(box, { key: 'Escape' });
    expect(onClose).not.toHaveBeenCalled();
    expect(box).toHaveValue('niezapisana notatka');
    const close = screen.getByRole('button', { name: 'Zamknij' });
    expect(close).toHaveFocus();
    fireEvent.keyDown(close, { key: 'Escape' });
    expect(onClose).toHaveBeenCalledTimes(1);
    onClose.mockClear();
    fireEvent.change(box, { target: { value: '' } });
    fireEvent.keyDown(box, { key: 'Escape' });
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('renders the status editor slot', () => {
    render(<FindingDetailPanel {...base} detail={detail()} statusEditor={<p>edytor</p>} />);
    expect(screen.getByText('edytor')).toBeInTheDocument();
  });

  it.each(['//evil.example/x.png', '/other/x.png', '/apix/x.png'])('does not load a screenshot from %s', (url) => {
    render(<FindingDetailPanel {...base} detail={detail({ screenshotUrl: url })} />);
    expect(screen.queryByRole('img', { name: /Zrzut ekranu/ })).toBeNull();
  });

  it('makes the rest of the page inert and locks scroll, and restores both on close', () => {
    const page = document.createElement('div');
    document.body.appendChild(page);
    const { unmount } = render(<FindingDetailPanel {...base} detail={detail()} />);
    expect(page).toHaveAttribute('inert');
    expect(screen.getByRole('dialog').closest('[inert]')).toBeNull();
    expect(document.body.style.overflow).toBe('hidden');
    unmount();
    expect(page).not.toHaveAttribute('inert');
    expect(document.body.style.overflow).toBe('');
    page.remove();
  });

  it('keeps focus inside the dialog when the refetch after a save fails', () => {
    const { rerender } = render(
      <FindingDetailPanel {...base} detail={detail()} statusEditor={<button type="button">Zapisz</button>} />,
    );
    const save = screen.getByRole('button', { name: 'Zapisz' });
    save.focus();
    expect(save).toHaveFocus();
    rerender(<FindingDetailPanel {...base} detail={detail()} isError statusEditor={<button type="button">Zapisz</button>} />);
    expect(screen.getByRole('alert')).toHaveTextContent('Nie udało się odświeżyć szczegółów');
    expect(save).toHaveFocus();
    expect(screen.getByRole('dialog')).toContainElement(document.activeElement as HTMLElement);
  });

  it('lifts inert from the page before focus goes back to the opener', () => {
    const opener = document.createElement('button');
    document.body.appendChild(opener);
    opener.focus();
    const focusSpy = vi.spyOn(opener, 'focus').mockImplementation(() => undefined);
    let inertAtFocus: boolean | undefined;
    const { unmount } = render(<FindingDetailPanel {...base} detail={detail()} />);
    expect(opener).toHaveAttribute('inert');
    focusSpy.mockImplementation(() => {
      inertAtFocus = opener.hasAttribute('inert');
    });
    unmount();
    expect(focusSpy).toHaveBeenCalledTimes(1);
    expect(inertAtFocus).toBe(false);
    focusSpy.mockRestore();
    opener.remove();
  });

  it('keeps the last detail with an inline alert when a refetch failed', () => {
    render(<FindingDetailPanel {...base} detail={detail()} isError />);
    expect(screen.getByRole('alert')).toHaveTextContent('Nie udało się odświeżyć szczegółów');
    expect(screen.getByRole('heading', { level: 2, name: 'Obietnica 18% zysku' })).toBeInTheDocument();
    expect(screen.getByRole('region', { name: /Naruszenia/ })).toBeInTheDocument();
  });

  describe('Eksportuj', () => {
    const exportUrl = 'http://localhost/api/findings/f1/export?format=html';

    it('links a loaded detail to its printable evidence pack in a new tab', () => {
      render(<FindingDetailPanel {...base} detail={detail({ exportUrl })} />);
      const link = within(screen.getByRole('dialog')).getByRole('link', { name: /^Eksportuj/ });
      expect(link).toHaveAttribute('href', exportUrl);
      expect(link).toHaveAttribute('target', '_blank');
      expect(link).toHaveAttribute('rel', 'noopener noreferrer');
    });

    it('keeps the link while a failed refetch shows the last detail', () => {
      render(<FindingDetailPanel {...base} isError detail={detail({ exportUrl })} />);
      expect(screen.getByRole('link', { name: /^Eksportuj/ })).toHaveAttribute('href', exportUrl);
    });

    // By text, not by role: an <a> without href has no link role and would slip through.
    it('shows no link while loading, on an error without data, or for an unknown finding', () => {
      const { rerender } = render(<FindingDetailPanel {...base} isLoading detail={undefined} />);
      expect(screen.queryByText(/Eksportuj/)).toBeNull();
      rerender(<FindingDetailPanel {...base} isError detail={undefined} />);
      expect(screen.queryByText(/Eksportuj/)).toBeNull();
      rerender(<FindingDetailPanel {...base} isError notFound detail={detail({ exportUrl })} />);
      expect(screen.queryByText(/Eksportuj/)).toBeNull();
    });
  });
});

describe('FindingDetailPanel rule grid', () => {
  it('shows the M2 rule grid built from the finding\'s rules', () => {
    render(<FindingDetailPanel detail={detail()} isLoading={false} isError={false} notFound={false} onClose={vi.fn()} />);
    const grid = screen.getByRole('region', { name: 'POKRYCIE REGUŁ M2 · 5 WYMOGÓW' });
    expect(within(grid).getAllByRole('button').map((b) => b.textContent)).toEqual(['R3', 'R12a', 'R1', 'R10', 'R9']);
  });

  it('shows no grid for M1 or M3, or an M2 finding without rules', () => {
    const { rerender } = render(
      <FindingDetailPanel detail={detail({ module: 'M1' })} isLoading={false} isError={false} notFound={false} onClose={vi.fn()} />,
    );
    expect(screen.queryByRole('region', { name: /POKRYCIE REGUŁ/ })).toBeNull();
    rerender(<FindingDetailPanel detail={detail({ module: 'M3' })} isLoading={false} isError={false} notFound={false} onClose={vi.fn()} />);
    expect(screen.queryByRole('region', { name: /POKRYCIE REGUŁ/ })).toBeNull();
    rerender(<FindingDetailPanel detail={detail({ rules: [] })} isLoading={false} isError={false} notFound={false} onClose={vi.fn()} />);
    expect(screen.queryByRole('region', { name: /POKRYCIE REGUŁ/ })).toBeNull();
  });
});


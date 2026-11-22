import { render, screen, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { ShortcutLegend } from './ShortcutLegend';

describe('ShortcutLegend', () => {
  it('is a closed disclosure named Skróty klawiszowe', () => {
    render(<ShortcutLegend />);
    const details = screen.getByText('Skróty klawiszowe').closest('details')!;
    expect(details).not.toHaveAttribute('open');
  });

  it('lists every shortcut with what it does', () => {
    render(<ShortcutLegend />);
    const terms = screen.getAllByRole('term').map((t) => t.textContent);
    expect(terms).toEqual(['J', 'K', '1', '2', '3', '4', '5', 'O', '/', 'Esc']);
    const meaning = (key: string) => within(screen.getByText(key, { selector: 'kbd' }).closest('div')!).getByRole('definition');
    expect(meaning('J')).toHaveTextContent('Następne zgłoszenie');
    expect(meaning('K')).toHaveTextContent('Poprzednie zgłoszenie');
    expect(meaning('1')).toHaveTextContent('Status: Nowe');
    expect(meaning('2')).toHaveTextContent('Status: W analizie');
    expect(meaning('3')).toHaveTextContent('Status: Potwierdzone');
    expect(meaning('4')).toHaveTextContent('Status: Fałszywy alarm');
    expect(meaning('5')).toHaveTextContent('Status: Zamknięte');
    expect(meaning('O')).toHaveTextContent('Otwórz źródło');
    expect(meaning('/')).toHaveTextContent('Szukaj');
    expect(meaning('Esc')).toHaveTextContent('Zamknij szczegóły');
  });
});

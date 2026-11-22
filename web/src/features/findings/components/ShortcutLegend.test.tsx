import { render, screen, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { ShortcutLegend } from './ShortcutLegend';

// The row of one action: its dt and the key chip(s) in its dd.
const row = (action: string) => screen.getByText(action).closest('div')!;

describe('ShortcutLegend', () => {
  it('is a closed disclosure named Skróty klawiszowe', () => {
    render(<ShortcutLegend />);
    const details = screen.getByText('Skróty klawiszowe').closest('details')!;
    expect(details).not.toHaveAttribute('open');
  });

  it('lists the five actions, each with its key chip as the sheet groups them', () => {
    render(<ShortcutLegend />);
    expect(screen.getAllByRole('term').map((t) => t.firstChild?.textContent)).toEqual([
      'Następne / poprzednie zgłoszenie',
      'Zmień status',
      'Otwórz źródło',
      'Szukaj',
      'Zamknij panel',
    ]);
    const chip = (action: string) => within(row(action)).getByRole('definition').querySelector('kbd')!;
    expect(chip('Następne / poprzednie zgłoszenie')).toHaveTextContent('J K');
    expect(chip('Zmień status')).toHaveTextContent('1 – 5');
    expect(chip('Otwórz źródło')).toHaveTextContent('O');
    expect(chip('Szukaj')).toHaveTextContent('/');
    expect(chip('Zamknij panel')).toHaveTextContent('Esc');
  });

  it('names the status behind each of the keys 1 to 5', () => {
    render(<ShortcutLegend />);
    expect(row('Zmień status')).toHaveTextContent('1 Nowe · 2 W analizie · 3 Potwierdzone · 4 Fałszywy alarm · 5 Zamknięte');
  });
});

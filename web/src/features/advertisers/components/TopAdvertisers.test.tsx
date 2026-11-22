import { fireEvent, render, screen, within } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import type { AdvertiserRow, Relation } from '../model';
import { TopAdvertisers } from './TopAdvertisers';

const a: AdvertiserRow = {
  key: 'h:@a',
  handle: '@a',
  count: 9,
  repeat: true,
  firms: [
    { key: 'rx', name: 'OKX', count: 5 },
    { key: 'ry', name: 'Nordic', count: 3 },
    { key: 'none', count: 1 },
  ],
};
const b: AdvertiserRow = { key: 'h:@b', handle: '@b', count: 1, repeat: false, firms: [{ key: 'rx', name: 'OKX', count: 1 }] };

function setup(selected: string | undefined = 'h:@a') {
  const props = {
    rows: [a, b],
    matchedFindings: 9,
    selected,
    onSelect: vi.fn(),
    relationHref: (r: Relation) => `/?rel_adv=${encodeURIComponent(r.advertiser)}#powiazania`,
    onOpenRelation: vi.fn(),
  };
  render(<TopAdvertisers {...props} />);
  return props;
}

describe('TopAdvertisers', () => {
  it('lists handle, matched firms, firm count and findings, with a text label for repeat advertisers', () => {
    setup();
    expect(screen.getByRole('heading', { name: 'Najczęstsi reklamodawcy' })).toBeInTheDocument();
    expect(screen.getByText('9 zgłoszeń z dopasowaną firmą · kliknij wiersz, by podświetlić relacje')).toBeInTheDocument();
    const rows = within(screen.getByRole('table')).getAllByRole('row').slice(1);
    const cells = within(rows[0]).getAllByRole('cell');
    expect(cells[0]).toHaveTextContent('@a (powtarzający się)OKX · Nordic');
    // Like the mockup, the side table shows the repeat by its red firm count; the text is for assistive tech.
    expect(within(cells[0]).getByText('(powtarzający się)')).toHaveClass('visually-hidden');
    expect(cells[1]).toHaveTextContent('2');
    expect(cells[1]).toHaveClass('adv-firms-repeat');
    expect(cells[2]).toHaveTextContent('9');
    expect(within(rows[1]).queryByText('(powtarzający się)')).toBeNull();
    expect(within(rows[1]).getAllByRole('cell')[1]).not.toHaveClass('adv-firms-repeat');
  });

  it('marks the selected row and selects another by click or by its button', () => {
    const props = setup();
    const rows = within(screen.getByRole('table')).getAllByRole('row').slice(1);
    expect(rows[0]).toHaveClass('selected');
    expect(screen.getByRole('button', { name: '@a' })).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByRole('button', { name: '@b' })).toHaveAttribute('aria-pressed', 'false');
    fireEvent.click(rows[1]);
    expect(props.onSelect).toHaveBeenLastCalledWith('h:@b');
    fireEvent.click(screen.getByRole('button', { name: '@b' }));
    expect(props.onSelect).toHaveBeenCalledTimes(2);
  });

  it('links to all findings of the selected advertiser', () => {
    const props = setup('h:@b');
    const link = screen.getByRole('link', { name: 'Zobacz zgłoszenia @b' });
    expect(link).toHaveAttribute('href', '/?rel_adv=h%3A%40b#powiazania');
    fireEvent.click(link);
    expect(props.onOpenRelation).toHaveBeenCalledWith({ advertiser: 'h:@b' });
  });
});

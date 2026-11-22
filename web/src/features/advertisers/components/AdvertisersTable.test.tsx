import { fireEvent, render, screen, within } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import type { AdvertiserRow, Relation } from '../model';
import { AdvertisersTable } from './AdvertisersTable';

const repeat: AdvertiserRow = {
  key: 'h:@a',
  name: 'Anna Inwestuje',
  handle: '@anna',
  count: 3,
  repeat: true,
  firms: [
    { key: 'rx', name: 'Firma X', count: 2 },
    { key: 'none', name: undefined, count: 1 },
  ],
};
const single: AdvertiserRow = { key: 'h:@b', name: 'Bartek', handle: '@b', count: 1, repeat: false, firms: [{ key: 'ry', name: 'Firma Y', count: 1 }] };

function props(rows: AdvertiserRow[] = [repeat, single]) {
  return { rows, relationHref: (r: Relation) => `/?rel_adv=${encodeURIComponent(r.advertiser)}&rel_firm=${encodeURIComponent(r.firm ?? '')}#powiazania`, onOpenRelation: vi.fn() };
}

describe('AdvertisersTable', () => {
  it('lists advertisers with their firms and counts in the given order', () => {
    render(<AdvertisersTable {...props()} />);
    const rows = within(screen.getByRole('table')).getAllByRole('row').slice(1);
    expect(rows).toHaveLength(2);
    expect(within(rows[0]).getByText('Anna Inwestuje')).toBeInTheDocument();
    expect(within(rows[0]).getByText('@anna')).toBeInTheDocument();
    expect(within(rows[0]).getByText('Firma X')).toBeInTheDocument();
    expect(within(rows[0]).getByText('bez dopasowanej firmy')).toBeInTheDocument();
    expect(within(rows[0]).getByText('3')).toBeInTheDocument();
    expect(within(rows[0]).getByText('2 zgłoszenia')).toBeInTheDocument();
    expect(within(rows[1]).getByText('Bartek')).toBeInTheDocument();
    expect(within(rows[1]).getByText('Firma Y')).toBeInTheDocument();
  });

  it('marks only repeat advertisers with a text label', () => {
    render(<AdvertisersTable {...props()} />);
    const rows = within(screen.getByRole('table')).getAllByRole('row').slice(1);
    expect(within(rows[0]).getByText('Powtarzający się')).toBeInTheDocument();
    expect(rows[0]).toHaveClass('repeat');
    expect(within(rows[1]).queryByText('Powtarzający się')).toBeNull();
    expect(rows[1]).not.toHaveClass('repeat');
  });



  it('renders an untrusted name as text in its own dir="auto" element', () => {
    const evil = '<img src=x onerror=alert(1)>‮evil';
    const { container } = render(<AdvertisersTable {...props([{ ...single, name: evil, handle: '@x‮' }])} />);
    expect(container.querySelector('img')).toBeNull();
    const name = screen.getByText(evil);
    expect(name).toHaveAttribute('dir', 'auto');
    expect(name.textContent).toBe(evil);
    expect(screen.getByText('@x‮')).toHaveAttribute('dir', 'auto');
  });

  it('shows the handle when the advertiser has no name', () => {
    render(<AdvertisersTable {...props([{ ...single, name: undefined }])} />);
    expect(screen.getAllByText('@b')).toHaveLength(1);
  });

  it('shows the contact as plain text when the advertiser has neither name nor handle', () => {
    const { container } = render(
      <AdvertisersTable {...props([{ ...single, name: undefined, handle: undefined, contact: 'https://p.example/x' }])} />,
    );
    expect(screen.getByText('https://p.example/x')).toHaveAttribute('dir', 'auto');
    // The scraped contact is never turned into a link; the only link is the firm's relation page.
    expect(container.querySelector('a[href*="p.example"]')).toBeNull();
  });


  it('opens the relation page of an advertiser and firm, including the unmatched findings', () => {
    const p = props();
    render(<AdvertisersTable {...p} />);
    const link = screen.getByRole('link', { name: 'Firma X' });
    expect(link).toHaveAttribute('href', '/?rel_adv=h%3A%40a&rel_firm=rx#powiazania');
    fireEvent.click(link);
    expect(p.onOpenRelation).toHaveBeenCalledWith({ advertiser: 'h:@a', firm: 'rx' });
    fireEvent.click(screen.getByRole('link', { name: 'bez dopasowanej firmy' }));
    expect(p.onOpenRelation).toHaveBeenLastCalledWith({ advertiser: 'h:@a', firm: 'none' });
  });
});

import { render, screen, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import type { AdvertiserRow, AdvertisersView } from '../model';
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

function view(patch: Partial<AdvertisersView> = {}): AdvertisersView {
  return { rows: [repeat, single], loaded: 11, total: 11, isLoading: false, isError: false, ...patch };
}

describe('AdvertisersTable', () => {
  it('lists advertisers with their firms and counts in the given order', () => {
    render(<AdvertisersTable {...view()} />);
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
    render(<AdvertisersTable {...view()} />);
    const rows = within(screen.getByRole('table')).getAllByRole('row').slice(1);
    expect(within(rows[0]).getByText('Powtarzający się')).toBeInTheDocument();
    expect(rows[0]).toHaveClass('repeat');
    expect(within(rows[1]).queryByText('Powtarzający się')).toBeNull();
    expect(rows[1]).not.toHaveClass('repeat');
  });

  it('states the findings it is based on and the cap', () => {
    render(<AdvertisersTable {...view()} />);
    expect(screen.getByText('Przeanalizowane zgłoszenia M1: 11 z 11 (limit 600).')).toBeInTheDocument();
    expect(screen.queryByText(/Starsze zgłoszenia pominięto/)).toBeNull();
  });

  it('says older findings are left out when the cap cut the list', () => {
    render(<AdvertisersTable {...view({ loaded: 600, total: 1000 })} />);
    expect(screen.getByText(/Przeanalizowane zgłoszenia M1: 600 z 1000 \(limit 600\)\. Starsze zgłoszenia pominięto\./)).toBeInTheDocument();
  });

  it('renders an untrusted name as text in its own dir="auto" element', () => {
    const evil = '<img src=x onerror=alert(1)>‮evil';
    const { container } = render(<AdvertisersTable {...view({ rows: [{ ...single, name: evil, handle: '@x‮' }] })} />);
    expect(container.querySelector('img')).toBeNull();
    const name = screen.getByText(evil);
    expect(name).toHaveAttribute('dir', 'auto');
    expect(name.textContent).toBe(evil);
    expect(screen.getByText('@x‮')).toHaveAttribute('dir', 'auto');
  });

  it('shows the handle when the advertiser has no name', () => {
    render(<AdvertisersTable {...view({ rows: [{ ...single, name: undefined }] })} />);
    expect(screen.getAllByText('@b')).toHaveLength(1);
  });

  it('shows the loading, error and empty states', () => {
    const { rerender } = render(<AdvertisersTable {...view({ rows: undefined, isLoading: true })} />);
    expect(screen.getByRole('status')).toHaveTextContent('Ładowanie');
    rerender(<AdvertisersTable {...view({ rows: undefined, isError: true })} />);
    expect(screen.getByRole('alert')).toHaveTextContent('Nie udało się pobrać danych o reklamodawcach.');
    expect(screen.queryByRole('table')).toBeNull();
    rerender(<AdvertisersTable {...view({ rows: [] })} />);
    expect(screen.getByRole('status')).toHaveTextContent('Brak reklamodawców w zgłoszeniach M1.');
    expect(screen.queryByRole('table')).toBeNull();
  });
});

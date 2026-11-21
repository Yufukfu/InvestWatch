import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import type { FindingRow, FindingStatus } from '../model';
import { FindingsTable } from './FindingsTable';

const row = (over: Partial<FindingRow> = {}): FindingRow => ({
  id: '1',
  module: 'M2',
  title: 'Obietnica zysku',
  platform: 'instagram',
  score: 0.5,
  status: 'in_review',
  ...over,
});

describe('FindingsTable', () => {
  it('renders one row per finding with Polish status and a two-decimal score, without a store', () => {
    render(<FindingsTable rows={[row(), row({ id: '2', title: 'Inny', score: 0.123, status: 'false_positive' })]} isLoading={false} isError={false} />);
    expect(screen.getAllByRole('row')).toHaveLength(3);
    expect(screen.getByText('Obietnica zysku')).toBeInTheDocument();
    expect(screen.getByText('0.50')).toBeInTheDocument();
    expect(screen.getByText('0.12')).toBeInTheDocument();
    expect(screen.getByText('W analizie')).toBeInTheDocument();
    expect(screen.getByText('Fałszywy alarm')).toBeInTheDocument();
    expect(screen.getAllByText('instagram')).toHaveLength(2);
    expect(screen.getAllByText('M2')).toHaveLength(2);
  });

  it.each<[FindingStatus, string]>([
    ['new', 'Nowe'],
    ['in_review', 'W analizie'],
    ['confirmed', 'Potwierdzone'],
    ['false_positive', 'Fałszywy alarm'],
    ['closed', 'Zamknięte'],
  ])('labels status %s as "%s"', (status, label) => {
    render(<FindingsTable rows={[row({ status })]} isLoading={false} isError={false} />);
    expect(screen.getByRole('cell', { name: label })).toBeInTheDocument();
  });

  it('shows the raw status for a value outside the contract', () => {
    render(<FindingsTable rows={[row({ status: 'archived' as FindingStatus })]} isLoading={false} isError={false} />);
    expect(screen.getByRole('cell', { name: 'archived' })).toBeInTheDocument();
  });

  it('shows the loading text', () => {
    render(<FindingsTable rows={undefined} isLoading isError={false} />);
    expect(screen.getByText('Ładowanie…')).toBeInTheDocument();
    expect(screen.queryByRole('table')).toBeNull();
  });

  it('shows the error alert on error', () => {
    render(<FindingsTable rows={undefined} isLoading={false} isError />);
    expect(screen.getByRole('alert')).toHaveTextContent('Nie udało się pobrać zgłoszeń.');
  });

  it('shows the error alert instead of stale rows when a refetch failed', () => {
    render(<FindingsTable rows={[row()]} isLoading={false} isError />);
    expect(screen.getByRole('alert')).toBeInTheDocument();
    expect(screen.queryByRole('table')).toBeNull();
  });

  it('shows the error alert when there are no rows and no error flag', () => {
    render(<FindingsTable rows={undefined} isLoading={false} isError={false} />);
    expect(screen.getByRole('alert')).toBeInTheDocument();
  });

  it('renders scraped markup as text, never as HTML', () => {
    const payload = '<img src=x onerror=alert(1)>Zysk 20%';
    render(<FindingsTable rows={[row({ title: payload })]} isLoading={false} isError={false} />);
    expect(screen.getByText(payload)).toBeInTheDocument();
    expect(document.querySelector('img')).toBeNull();
  });
});

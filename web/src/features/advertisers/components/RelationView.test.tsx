import { fireEvent, render, screen, within } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import type { AdvertiserFinding, AdvertiserRow, Relation } from '../model';
import { RelationView } from './RelationView';

const row: AdvertiserRow = {
  key: 'h:@a',
  handle: '@a',
  count: 9,
  repeat: true,
  firms: [
    { key: 'rx', name: 'OKX Europe', count: 5 },
    { key: 'ry', name: 'Nordic Brokers', count: 3 },
    { key: 'none', count: 1 },
  ],
};
const finding = (id: string, patch: Partial<AdvertiserFinding> = {}): AdvertiserFinding => ({
  id,
  module: 'M1',
  title: `Tytuł ${id}`,
  platform: 'instagram',
  score: 0.93,
  riskLevel: 'high',
  detectedAt: '2026-11-22T23:52:00Z',
  ...patch,
});

function setup(relation: Relation, patch: Partial<Parameters<typeof RelationView>[0]> = {}) {
  const props = {
    relation,
    row,
    findings: [finding('f1'), finding('f2', { riskLevel: 'medium', platform: 'youtube', score: 0.64, detectedAt: '2026-11-17T09:30:00Z' })],
    onBack: vi.fn(),
    onOpenFinding: vi.fn(),
    relationHref: (r: Relation) => `/?rel_adv=${r.advertiser}&rel_firm=${r.firm ?? ''}#powiazania`,
    onOpenRelation: vi.fn(),
    ...patch,
  };
  render(<RelationView {...props} />);
  return props;
}

describe('RelationView', () => {
  it('shows the count, the advertiser and the firm of the relation', () => {
    setup({ advertiser: 'h:@a', firm: 'rx' });
    expect(screen.getByText('WYBRANA RELACJA')).toBeInTheDocument();
    expect(screen.getByRole('heading', { level: 2 })).toHaveTextContent('2 zgłoszenia: @a → promuje OKX Europe');
  });

  it('lists the other firms of the advertiser as links to their relations', () => {
    const p = setup({ advertiser: 'h:@a', firm: 'rx' });
    expect(screen.getByText(/Ten sam reklamodawca promuje jeszcze/).textContent).toBe(
      'Ten sam reklamodawca promuje jeszcze 1 firmę: Nordic Brokers (3)',
    );
    fireEvent.click(screen.getByRole('link', { name: 'Nordic Brokers' }));
    expect(p.onOpenRelation).toHaveBeenCalledWith({ advertiser: 'h:@a', firm: 'ry' });
    fireEvent.click(screen.getByRole('link', { name: 'Pokaż cały profil reklamodawcy' }));
    expect(p.onOpenRelation).toHaveBeenLastCalledWith({ advertiser: 'h:@a' });
  });

  it('shows the whole profile without a firm', () => {
    setup({ advertiser: 'h:@a' });
    expect(screen.getByText('WYBRANY REKLAMODAWCA')).toBeInTheDocument();
    expect(screen.getByRole('heading', { level: 2 })).toHaveTextContent('2 zgłoszenia: @a');
    expect(screen.getByText(/Reklamodawca promuje/).textContent).toBe('Reklamodawca promuje 2 firmy: OKX Europe (5), Nordic Brokers (3)');
    expect(screen.queryByRole('link', { name: /Pokaż cały profil/ })).toBeNull();
  });

  it('lists the findings with risk text, platform, score and time, and opens one', () => {
    const p = setup({ advertiser: 'h:@a', firm: 'rx' });
    const rows = within(screen.getByRole('table')).getAllByRole('row').slice(1);
    expect(rows.map((r) => within(r).getAllByRole('cell').map((c) => c.textContent))).toEqual([
      ['Wysoki', 'Tytuł f1', 'Instagram', '0,93', '22.11.2026 · 23:52'],
      ['Średni', 'Tytuł f2', 'YouTube', '0,64', '17.11.2026 · 09:30'],
    ]);
    fireEvent.click(screen.getByRole('button', { name: 'Tytuł f2' }));
    expect(p.onOpenFinding).toHaveBeenCalledWith('f2');
  });

  it('goes back to the graph', () => {
    const p = setup({ advertiser: 'h:@a', firm: 'rx' });
    fireEvent.click(screen.getByRole('button', { name: 'Powiązania' }));
    expect(p.onBack).toHaveBeenCalled();
  });

  it('says so when the relation is not in the loaded data', () => {
    setup({ advertiser: 'h:@gone' }, { row: undefined, findings: [] });
    expect(screen.getByRole('status')).toHaveTextContent('Nie znaleziono tej relacji');
    expect(screen.getByRole('button', { name: 'Powiązania' })).toBeInTheDocument();
  });

  it('keeps untrusted handle, firm name and title as text in their own dir="auto" element', () => {
    const evil = '<img src=x onerror=alert(1)>‮evil';
    const { container } = render(
      <RelationView
        relation={{ advertiser: 'h:x', firm: 'rx' }}
        row={{ ...row, handle: evil, firms: [{ key: 'rx', name: evil, count: 1 }, { key: 'ry', name: evil, count: 1 }] }}
        findings={[finding('f1', { title: evil })]}
        onBack={vi.fn()}
        onOpenFinding={vi.fn()}
        relationHref={() => '#'}
        onOpenRelation={vi.fn()}
      />,
    );
    expect(container.querySelector('img')).toBeNull();
    const nodes = screen.getAllByText(evil);
    expect(nodes.length).toBe(4);
    for (const node of nodes) expect(node).toHaveAttribute('dir', 'auto');
  });
});

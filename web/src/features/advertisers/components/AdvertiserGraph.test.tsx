import { fireEvent, render, screen, within } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { aggregateAdvertisers } from '../aggregate';
import { buildGraph } from '../graph';
import type { AdvertiserFinding } from '../model';
import { AdvertiserGraph } from './AdvertiserGraph';

let n = 0;
const f = (handle: string, firm: string | null): AdvertiserFinding => ({
  id: `c-${++n}`,
  module: 'M1',
  advertiser: { handle },
  firm: firm ? { name: firm, registryId: `r-${firm}` } : null,
});
const findings = [f('@a', 'X'), f('@a', 'Y'), f('@a', 'X'), f('@b', 'X'), f('@c', null)];
const graph = buildGraph(aggregateAdvertisers(findings));

describe('AdvertiserGraph', () => {
  it('labels both columns with counts and describes itself for assistive technology', () => {
    render(<AdvertiserGraph graph={graph} selected={undefined} onOpenRelation={vi.fn()} />);
    const left = screen.getByRole('list', { name: 'Reklamodawcy' });
    expect(within(left).getAllByRole('listitem').map((li) => li.textContent)).toEqual(['@a3', '@b1']);
    const right = screen.getByRole('list', { name: 'Firmy z rejestru' });
    expect(within(right).getAllByRole('listitem').map((li) => li.textContent).sort()).toEqual(['1Y', '3X']);
    expect(screen.getByRole('img')).toHaveAccessibleName(/Graf powiązań: 2 reklamodawców, 2 firmy, 3 relacje\. Te same dane są w widoku Tabela\./);
    expect(screen.getByText(/1 bez dopasowanej firmy/)).toBeInTheDocument();
  });

  it('draws repeat edges red and single ones grey, with thickness by count', () => {
    const { container } = render(<AdvertiserGraph graph={graph} selected={undefined} onOpenRelation={vi.fn()} />);
    const ax = container.querySelector('[data-edge="h:@a|r-X"]');
    const bx = container.querySelector('[data-edge="h:@b|r-X"]');
    expect(ax).toHaveClass('adv-edge-repeat');
    expect(bx).toHaveClass('adv-edge-single');
    const width = (g: Element | null) => Number(g?.querySelector('.adv-edge-line')?.getAttribute('stroke-width'));
    expect(width(ax)).toBeGreaterThan(width(bx));
  });

  it('highlights the selected advertiser and fades the other edges', () => {
    const { container } = render(<AdvertiserGraph graph={graph} selected="h:@b" onOpenRelation={vi.fn()} />);
    expect(container.querySelector('[data-edge="h:@b|r-X"]')).toHaveClass('adv-edge-selected');
    expect(container.querySelector('[data-edge="h:@a|r-X"]')).toHaveClass('adv-edge-dim');
    // Drawn last, so it is on top.
    const groups = [...container.querySelectorAll('[data-edge]')];
    expect(groups.at(-1)).toHaveAttribute('data-edge', 'h:@b|r-X');
  });

  it("draws the selected advertiser's edges after the others", () => {
    const { container } = render(<AdvertiserGraph graph={graph} selected="h:@a" onOpenRelation={vi.fn()} />);
    const order = [...container.querySelectorAll('[data-edge]')].map((g) => g.getAttribute('data-edge'));
    expect(order).toEqual(['h:@b|r-X', 'h:@a|r-X', 'h:@a|r-Y']);
  });

  it('opens the relation of a clicked edge', () => {
    const onOpen = vi.fn();
    const { container } = render(<AdvertiserGraph graph={graph} selected={undefined} onOpenRelation={onOpen} />);
    fireEvent.click(container.querySelector('[data-edge="h:@a|r-Y"]')!);
    expect(onOpen).toHaveBeenCalledWith({ advertiser: 'h:@a', firm: 'r-Y' });
  });

  it('keeps untrusted handles and firm names as text in their own dir="auto" element', () => {
    const evil = '<b>x</b>‮evil';
    const g = buildGraph(aggregateAdvertisers([f(evil, evil)]));
    const { container } = render(<AdvertiserGraph graph={g} selected={undefined} onOpenRelation={vi.fn()} />);
    expect(container.querySelector('b')).toBeNull();
    const nodes = screen.getAllByText(evil);
    expect(nodes).toHaveLength(2);
    for (const node of nodes) expect(node).toHaveAttribute('dir', 'auto');
    // The edge tooltip isolates both values.
    expect(container.querySelector('title')?.textContent).toBe(`⁨${evil}⁩ → ⁨${evil}⁩: 1`);
  });
});

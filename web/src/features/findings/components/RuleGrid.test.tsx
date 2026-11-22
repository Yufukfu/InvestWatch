import { render, screen, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import type { RuleView } from '../model';
import { RuleGrid } from './RuleGrid';

const rule = (ruleId: string, result: RuleView['result'], legalBasis: string | null = `art. ${ruleId}`): RuleView => ({
  ruleId,
  name: `Wymóg ${ruleId}`,
  result,
  severity: 'medium',
  legalBasis,
});

const RULES: RuleView[] = [
  rule('R1', 'fail'),
  rule('R2', 'pass'),
  rule('R3', 'uncertain'),
  rule('R4', 'not_applicable'),
  rule('R5', 'fail'),
  rule('R6', 'pass'),
  rule('R7', 'pass', null),
];

describe('RuleGrid', () => {
  it('titles the grid with the number of rules and draws one square per rule in API order', () => {
    render(<RuleGrid rules={RULES} />);
    const grid = screen.getByRole('region', { name: 'POKRYCIE REGUŁ M2 · 7 WYMOGÓW' });
    const squares = within(grid).getAllByRole('button');
    expect(squares.map((s) => s.textContent)).toEqual(['R1', 'R2', 'R3', 'R4', 'R5', 'R6', 'R7']);
    expect(squares.map((s) => s.className.match(/cell-(\w+)/)?.[1])).toEqual([
      'fail',
      'pass',
      'uncertain',
      'not_applicable',
      'fail',
      'pass',
      'pass',
    ]);
    expect(grid).toHaveTextContent('Najedź na pole lub przejdź do niego klawiszem Tab, aby zobaczyć podstawę prawną');
  });

  it('counts every result in the legend, zero included', () => {
    render(<RuleGrid rules={RULES.filter((r) => r.result !== 'uncertain')} />);
    const legend = screen.getByRole('list', { name: 'Legenda' });
    expect(within(legend).getAllByRole('listitem').map((li) => li.textContent)).toEqual([
      'Naruszenie 2',
      'Niepewne 0',
      'Zgodne 3',
      'Nie dotyczy 1',
    ]);
  });

  it('names each square with the rule id, the result in Polish and the legal basis', () => {
    render(<RuleGrid rules={RULES} />);
    const names = screen.getAllByRole('button').map((b) => b.getAttribute('aria-label')?.replace(/[⁨⁩]/g, ''));
    expect(names[0]).toBe('R1, Wymóg R1: Naruszenie. Podstawa prawna: art. R1');
    expect(names[2]).toBe('R3, Wymóg R3: Niepewne. Podstawa prawna: art. R3');
    expect(names[3]).toBe('R4, Wymóg R4: Nie dotyczy. Podstawa prawna: art. R4');
    expect(names[1]).toBe('R2, Wymóg R2: Zgodne. Podstawa prawna: art. R2');
    expect(names[6]).toBe('R7, Wymóg R7: Zgodne. Podstawa prawna: brak podstawy prawnej');
  });

  it('isolates the API strings in the name', () => {
    render(<RuleGrid rules={[rule('R1', 'fail', 'art. 1‮evil')]} />);
    const name = screen.getByRole('button').getAttribute('aria-label')!;
    expect(name).toContain('⁨R1⁩');
    expect(name).toContain('⁨art. 1‮evil⁩');
  });

  it('puts the legal basis in a tooltip next to its square, as text with dir="auto"', () => {
    render(<RuleGrid rules={RULES} />);
    const square = screen.getAllByRole('button')[0];
    const tip = square.parentElement!.querySelector('[role="tooltip"]')!;
    expect(tip).toHaveTextContent('R1 · Naruszenie');
    expect(within(tip as HTMLElement).getByText('art. R1')).toHaveAttribute('dir', 'auto');
    const last = screen.getAllByRole('button')[6].parentElement!.querySelector('[role="tooltip"]')!;
    expect(last).toHaveTextContent('brak podstawy prawnej');
  });

  it('keeps markup in the legal basis as text', () => {
    render(<RuleGrid rules={[rule('R1', 'fail', '<img src=x onerror=alert(1)>')]} />);
    expect(screen.getByText('<img src=x onerror=alert(1)>')).toBeInTheDocument();
    expect(document.querySelector('img')).toBeNull();
  });

  it('renders nothing without rules', () => {
    const { container } = render(<RuleGrid rules={[]} />);
    expect(container).toBeEmptyDOMElement();
  });
});

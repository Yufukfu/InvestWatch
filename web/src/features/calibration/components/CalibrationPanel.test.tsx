import { fireEvent, render, screen, within } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import calM2 from '../../../test/fixtures/calibration-M2.json';
import type { CalibrationView } from '../model';
import { CalibrationPanel, type CalibrationPanelProps } from './CalibrationPanel';

const view: CalibrationView = { module: 'M2', currentThreshold: 0.5, labeledSamples: 70, points: calM2.points };
const i50 = calM2.points.findIndex((p) => p.threshold === 0.5);
const i70 = calM2.points.findIndex((p) => p.threshold === 0.7);

function setup(over: Partial<CalibrationPanelProps> = {}) {
  const props: CalibrationPanelProps = {
    module: 'M2',
    onModule: vi.fn(),
    view,
    isLoading: false,
    isError: false,
    index: i50,
    currentIndex: i50,
    onIndex: vi.fn(),
    canSave: true,
    onSave: vi.fn(),
    isSaving: false,
    saved: false,
    error: undefined,
    chartSize: { width: 500, height: 240 },
    ...over,
  };
  render(<CalibrationPanel {...props} />);
  return props;
}

const metric = (name: string) => screen.getByRole('group', { name });

describe('CalibrationPanel', () => {
  it('switches modules with pressed buttons, M2 first', () => {
    const p = setup();
    const group = screen.getByRole('group', { name: 'Moduł' });
    const buttons = within(group).getAllByRole('button');
    expect(buttons.map((b) => b.textContent)).toEqual(['M2 · Zgodność reklam', 'M1 · Finfluencerzy', 'M3 · Usługi bez zezwolenia']);
    expect(buttons[0]).toHaveAttribute('aria-pressed', 'true');
    fireEvent.click(buttons[2]);
    expect(p.onModule).toHaveBeenCalledWith('M3');
  });

  it('has a labelled slider over the point indexes with the threshold as its value text', () => {
    const p = setup({ index: i70 });
    const slider = screen.getByRole('slider', { name: 'Próg dla M2' });
    expect(slider).toHaveAttribute('min', '0');
    expect(slider).toHaveAttribute('max', String(calM2.points.length - 1));
    expect(slider).toHaveValue(String(i70));
    expect(slider).toHaveAttribute('aria-valuetext', 'próg 0.70');
    fireEvent.change(slider, { target: { value: String(i50) } });
    expect(p.onIndex).toHaveBeenCalledWith(i50);
    expect(screen.getByText('0.70', { selector: '.threshold-selected' })).toBeInTheDocument();
    expect(screen.getByText(/obecny próg: 0\.50/)).toBeInTheDocument();
    expect(screen.getByText(/70 oznaczonych próbek/)).toBeInTheDocument();
  });

  it('shows the selected point next to the current one, as returned', () => {
    setup({ index: i70 });
    expect(metric('Fałszywe alarmy (FP)')).toHaveTextContent('0');
    expect(metric('Fałszywe alarmy (FP)')).toHaveTextContent('obecnie 5');
    expect(metric('Przeoczone (FN)')).toHaveTextContent('7');
    expect(metric('Przeoczone (FN)')).toHaveTextContent('obecnie 0');
    expect(metric('Wykryte naruszenia (TP)')).toHaveTextContent('23');
    expect(metric('Poprawnie pominięte (TN)')).toHaveTextContent('40');
    expect(metric('Precyzja')).toHaveTextContent('100%');
    expect(metric('Precyzja')).toHaveTextContent('obecnie 85,7%');
    expect(metric('Czułość')).toHaveTextContent('76,7%');
    expect(metric('F1')).toHaveTextContent('86,8%');
  });

  it('omits F1 when the point has none', () => {
    const points = calM2.points.map(({ f1: _f1, ...p }) => p);
    setup({ view: { ...view, points } });
    expect(screen.queryByRole('group', { name: 'F1' })).toBeNull();
  });

  it('saves only when the selection differs and warns that it is global', () => {
    setup({ index: i50 });
    const save = screen.getByRole('button', { name: 'Zapisz próg' });
    expect(save).toBeDisabled();
    expect(screen.queryByRole('status')).toBeNull();
    expect(screen.getByText(/zmienia poziom ryzyka wszystkich zgłoszeń modułu M2 i próg alertów/)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Wróć do obecnego' })).toBeNull();
  });

  it('save and reset call back with the selection', () => {
    const p = setup({ index: i70 });
    fireEvent.click(screen.getByRole('button', { name: 'Zapisz próg' }));
    expect(p.onSave).toHaveBeenCalledWith(0.7);
    fireEvent.click(screen.getByRole('button', { name: 'Wróć do obecnego' }));
    expect(p.onIndex).toHaveBeenCalledWith(i50);
  });

  it('cannot save before the thresholds are known or while saving', () => {
    setup({ index: i70, canSave: false });
    expect(screen.getByRole('button', { name: 'Zapisz próg' })).toBeDisabled();
  });

  it('disables the save while saving', () => {
    setup({ index: i70, isSaving: true });
    expect(screen.getByRole('button', { name: 'Zapisywanie…' })).toBeDisabled();
  });

  it('confirms a save', () => {
    setup({ saved: true, error: undefined });
    expect(screen.getByRole('status')).toHaveTextContent('Zapisano. Poziomy ryzyka zostały przeliczone.');
  });

  it('shows an error alert', () => {
    setup({ index: i70, error: 'Nie zapisano progu: serwer odrzucił wartość.' });
    expect(screen.getByRole('alert')).toHaveTextContent('Nie zapisano progu: serwer odrzucił wartość.');
  });

  it('marks the selected threshold apart from the current one, once when they are equal', () => {
    setup({ index: i70 });
    expect(document.querySelectorAll('.recharts-reference-line')).toHaveLength(2);
  });

  it('draws one marker when the selection is the current threshold', () => {
    setup({ index: i50 });
    expect(document.querySelectorAll('.recharts-reference-line')).toHaveLength(1);
  });

  it('draws the chart with a text alternative', () => {
    setup({ index: i70 });
    expect(screen.getByRole('img', { name: /Precyzja i czułość/ })).toBeInTheDocument();
    expect(document.querySelectorAll('path.recharts-line-curve')).toHaveLength(2);
    const table = within(screen.getByText('Pokaż dane w tabeli').closest('details')!).getByRole('table');
    expect(within(table).getAllByRole('row')).toHaveLength(calM2.points.length + 1);
    expect(within(table).getAllByRole('columnheader').map((h) => h.textContent)).toEqual(['Próg', 'Precyzja', 'Czułość', 'FP', 'FN']);
  });

  it('shows loading, error and no-data states without slider or save', () => {
    const { unmount } = render(<CalibrationPanel {...setupProps({ view: undefined, isLoading: true })} />);
    expect(screen.getByText('Ładowanie kalibracji…')).toBeInTheDocument();
    unmount();
    render(<CalibrationPanel {...setupProps({ view: undefined, isError: true })} />);
    expect(screen.getByRole('alert')).toHaveTextContent('Nie udało się pobrać kalibracji.');
    expect(screen.getByRole('group', { name: 'Moduł' })).toBeInTheDocument();
    expect(screen.queryByRole('slider')).toBeNull();
  });

  it.each([
    ['no labelled samples', { labeledSamples: 0 }, i50],
    ['no points', { points: [] }, -1],
  ])('says there is not enough data when %s', (_name, patch, index) => {
    render(<CalibrationPanel {...setupProps({ view: { ...view, ...patch }, index, currentIndex: index })} />);
    expect(screen.getByText('Za mało oznaczonych danych, aby skalibrować ten moduł.')).toBeInTheDocument();
    expect(screen.queryByRole('slider')).toBeNull();
    expect(screen.queryByRole('button', { name: 'Zapisz próg' })).toBeNull();
  });
});

function setupProps(over: Partial<CalibrationPanelProps>): CalibrationPanelProps {
  return {
    module: 'M2',
    onModule: vi.fn(),
    view,
    isLoading: false,
    isError: false,
    index: i50,
    currentIndex: i50,
    onIndex: vi.fn(),
    canSave: true,
    onSave: vi.fn(),
    isSaving: false,
    saved: false,
    error: undefined,
    chartSize: { width: 500, height: 240 },
    ...over,
  };
}

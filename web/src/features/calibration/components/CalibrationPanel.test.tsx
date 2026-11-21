import { fireEvent, render, screen, within } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import calM2 from '../../../test/fixtures/calibration-M2.json';
import type { CalibrationView } from '../model';
import { CalibrationPanel, type CalibrationPanelProps } from './CalibrationPanel';

const view: CalibrationView = { module: 'M2', currentThreshold: 0.5, labeledSamples: 70, points: calM2.points };
const i50 = calM2.points.findIndex((p) => p.threshold === 0.5);
const i70 = calM2.points.findIndex((p) => p.threshold === 0.7);
const SAVED = 'Zapisano. Poziomy ryzyka zostały przeliczone.';

function setup(over: Partial<CalibrationPanelProps> = {}) {
  const props = setupProps(over);
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

  it('does not switch module while a save is in flight', () => {
    const p = setup({ isSaving: true, index: i70 });
    const m1 = screen.getByRole('button', { name: 'M1 · Finfluencerzy' });
    expect(m1).toHaveAttribute('aria-disabled', 'true');
    fireEvent.click(m1);
    expect(p.onModule).not.toHaveBeenCalled();
  });

  it('has a labelled slider over the point indexes with the threshold as its value text', () => {
    const p = setup({ index: i70 });
    const slider = screen.getByRole('slider', { name: 'Próg dla M2' });
    expect(slider).toHaveAttribute('min', '0');
    expect(slider).toHaveAttribute('max', String(calM2.points.length - 1));
    expect(slider).toHaveValue(String(i70));
    expect(slider).toHaveAttribute('aria-valuetext', 'próg 0,70');
    fireEvent.change(slider, { target: { value: String(i50) } });
    expect(p.onIndex).toHaveBeenCalledWith(i50);
    expect(screen.getByText('0,70', { selector: '.threshold-selected' })).toBeInTheDocument();
    expect(screen.getByText(/obecny próg: 0,50/)).toBeInTheDocument();
    expect(screen.getByText(/Liczba oznaczonych próbek: 70/)).toBeInTheDocument();
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

  it('a current threshold off the curve: compares with the nearest point, says so, and has nothing to save yet', () => {
    const i60 = calM2.points.findIndex((p) => p.threshold === 0.6);
    setup({ view: { ...view, currentThreshold: 0.62 }, index: i60, currentIndex: i60 });
    expect(screen.getByText(/obecny próg: 0,62/)).toBeInTheDocument();
    expect(metric('Fałszywe alarmy (FP)')).toHaveTextContent('najbliższy punkt (0,60) ');
    expect(screen.getByRole('button', { name: 'Zapisz próg' })).toHaveAttribute('aria-disabled', 'true');
    expect(screen.getByRole('button', { name: 'Wróć do obecnego' })).toHaveAttribute('aria-disabled', 'true');
  });

  it('omits F1 when the point has none', () => {
    const points = calM2.points.map(({ f1: _f1, ...p }) => p);
    setup({ view: { ...view, points } });
    expect(screen.queryByRole('group', { name: 'F1' })).toBeNull();
  });

  it('saves only when the selection differs and warns that it is global', () => {
    setup({ index: i50 });
    const save = screen.getByRole('button', { name: 'Zapisz próg' });
    expect(save).toHaveAttribute('aria-disabled', 'true');
    expect(save).toHaveAccessibleDescription(/zmienia poziom ryzyka wszystkich zgłoszeń modułu M2/);
    expect(screen.getByText(/zmienia poziom ryzyka wszystkich zgłoszeń modułu M2 i próg alertów/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Wróć do obecnego' })).toHaveAttribute('aria-disabled', 'true');
  });

  it('names the module in the warning for the module on screen', () => {
    setup({ module: 'M3', index: i50 });
    expect(screen.getByText(/zmienia poziom ryzyka wszystkich zgłoszeń modułu M3 i próg alertów/)).toBeInTheDocument();
  });

  it('save and reset call back with the selection', () => {
    const p = setup({ index: i70 });
    fireEvent.click(screen.getByRole('button', { name: 'Zapisz próg' }));
    expect(p.onSave).toHaveBeenCalledWith(0.7);
    fireEvent.click(screen.getByRole('button', { name: 'Wróć do obecnego' }));
    expect(p.onIndex).toHaveBeenCalledWith(i50);
  });

  it('an aria-disabled save or reset does nothing when clicked', () => {
    const p = setup({ index: i50 });
    fireEvent.click(screen.getByRole('button', { name: 'Zapisz próg' }));
    fireEvent.click(screen.getByRole('button', { name: 'Wróć do obecnego' }));
    expect(p.onSave).not.toHaveBeenCalled();
    expect(p.onIndex).not.toHaveBeenCalled();
  });

  it('cannot save before the thresholds are known or while saving', () => {
    const p = setup({ index: i70, canSave: false });
    expect(screen.getByRole('button', { name: 'Zapisz próg' })).toHaveAttribute('aria-disabled', 'true');
    fireEvent.click(screen.getByRole('button', { name: 'Zapisz próg' }));
    expect(p.onSave).not.toHaveBeenCalled();
  });

  it('disables the save while saving', () => {
    const p = setup({ index: i70, isSaving: true });
    expect(screen.getByRole('button', { name: 'Zapisywanie…' })).toHaveAttribute('aria-disabled', 'true');
    fireEvent.click(screen.getByRole('button', { name: 'Zapisywanie…' }));
    expect(p.onSave).not.toHaveBeenCalled();
  });

  it('keeps the live region mounted and fills its text only after a save', () => {
    const { rerender } = render(<CalibrationPanel {...setupProps({})} />);
    const region = screen.getByRole('status');
    expect(region).toHaveTextContent('');
    rerender(<CalibrationPanel {...setupProps({ saved: true })} />);
    expect(screen.getByRole('status')).toBe(region);
    expect(region).toHaveTextContent(SAVED);
  });

  it('confirms a save', () => {
    setup({ saved: true, error: undefined });
    expect(screen.getByRole('status')).toHaveTextContent(SAVED);
  });

  it('hides the confirmation once the slider moves off the saved point', () => {
    setup({ saved: true, index: i70, currentIndex: i50 });
    expect(screen.getByRole('status')).toHaveTextContent('');
    expect(screen.queryByText(/Zapisano/)).toBeNull();
  });

  it('does not confirm a save that also reports an error', () => {
    setup({ saved: true, error: 'Nie zapisano progu: błąd serwera.' });
    expect(screen.getByRole('status')).toHaveTextContent('');
    expect(screen.getByRole('alert')).toHaveTextContent('Nie zapisano progu: błąd serwera.');
  });

  it('shows an error alert', () => {
    setup({ index: i70, error: 'Nie zapisano progu: serwer odrzucił wartość.' });
    expect(screen.getByRole('alert')).toHaveTextContent('Nie zapisano progu: serwer odrzucił wartość.');
  });

  it('explains that saving is unavailable when the thresholds could not be loaded', () => {
    setup({ view: undefined, settingsError: true, isError: false, isLoading: false });
    expect(screen.getByRole('alert')).toHaveTextContent('Nie udało się pobrać progów; zapis jest niedostępny.');
  });

  it('marks the selected threshold apart from the current one, once when they are equal', () => {
    setup({ index: i70 });
    expect(document.querySelectorAll('.recharts-reference-line')).toHaveLength(2);
  });

  it('draws one marker when the selection is the current threshold', () => {
    setup({ index: i50 });
    expect(document.querySelectorAll('.recharts-reference-line')).toHaveLength(1);
  });

  it('draws the chart with a text alternative and labels both markers', () => {
    setup({ index: i70 });
    const plot = screen.getByRole('img', { name: /Precyzja i czułość/ });
    expect(plot).toHaveAttribute('aria-label', 'Precyzja i czułość w zależności od progu; obecny 0,50, wybrany 0,70');
    expect(plot).toHaveTextContent('obecny');
    expect(plot).toHaveTextContent('wybrany');
    expect(document.querySelectorAll('path.recharts-line-curve')).toHaveLength(2);
    const table = within(screen.getByText('Pokaż dane w tabeli').closest('details')!).getByRole('table');
    expect(within(table).getAllByRole('row')).toHaveLength(calM2.points.length + 1);
    expect(within(table).getAllByRole('columnheader').map((h) => h.textContent)).toEqual(['Próg', 'Precyzja', 'Czułość', 'FP', 'FN']);
  });

  it('the text alternative shows precision, recall, FP and FN of each point in the right columns', () => {
    setup({ index: i70 });
    const table = within(screen.getByText('Pokaż dane w tabeli').closest('details')!).getByRole('table');
    const row = within(table).getByRole('rowheader', { name: '0,70' }).closest('tr')!;
    expect(within(row).getAllByRole('cell').map((c) => c.textContent)).toEqual(['100%', '76,7%', '0', '7']);
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

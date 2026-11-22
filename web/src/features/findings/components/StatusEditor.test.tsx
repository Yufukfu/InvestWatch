import { fireEvent, render, screen, within } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { StatusEditor } from './StatusEditor';

const base = { status: 'new' as const, note: null, isSaving: false, error: undefined, saved: false };

describe('StatusEditor', () => {
  const choose = (label: string) => fireEvent.click(screen.getByRole('radio', { name: label }));

  it('offers all five statuses as a radio group and starts at the saved one', () => {
    render(<StatusEditor {...base} onSave={vi.fn()} />);
    const group = screen.getByRole('radiogroup', { name: 'Status' });
    const radios = within(group).getAllByRole('radio');
    expect(radios.map((r) => r.getAttribute('value'))).toEqual(['new', 'in_review', 'confirmed', 'false_positive', 'closed']);
    expect(radios.map((r) => (r as HTMLInputElement).checked)).toEqual([true, false, false, false, false]);
    expect(screen.getByRole('radio', { name: 'Fałszywy alarm' })).toBeInTheDocument();
  });

  it('uses native radios that share one name, so the arrow keys move between them', () => {
    render(<StatusEditor {...base} onSave={vi.fn()} />);
    const radios = screen.getAllByRole('radio');
    expect(radios.every((r) => r.getAttribute('name') === radios[0].getAttribute('name'))).toBe(true);
    expect(radios.every((r) => r.tagName === 'INPUT' && r.getAttribute('type') === 'radio')).toBe(true);
  });

  it('saves the chosen status and note', () => {
    const onSave = vi.fn();
    render(<StatusEditor {...base} onSave={onSave} />);
    const save = screen.getByRole('button', { name: 'Zapisz decyzję' });
    expect(save).toHaveAttribute('aria-disabled', 'true');
    choose('Potwierdzone');
    fireEvent.change(screen.getByLabelText('Notatka'), { target: { value: 'Potwierdzone ręcznie' } });
    expect(save).toHaveAttribute('aria-disabled', 'false');
    fireEvent.click(save);
    expect(onSave).toHaveBeenCalledWith({ status: 'confirmed', note: 'Potwierdzone ręcznie' });
  });

  it('sends only the note when the status is unchanged, and an emptied note as null', () => {
    const onSave = vi.fn();
    render(<StatusEditor {...base} note="stara" onSave={onSave} />);
    fireEvent.change(screen.getByLabelText('Notatka'), { target: { value: '  ' } });
    fireEvent.click(screen.getByRole('button', { name: 'Zapisz decyzję' }));
    expect(onSave).toHaveBeenCalledWith({ note: null });
  });

  it('sends only the status when the note is unchanged', () => {
    const onSave = vi.fn();
    render(<StatusEditor {...base} note="n" onSave={onSave} />);
    choose('Zamknięte');
    fireEvent.click(screen.getByRole('button', { name: 'Zapisz decyzję' }));
    expect(onSave).toHaveBeenCalledWith({ status: 'closed' });
  });

  it('disables the controls while saving', () => {
    render(<StatusEditor {...base} isSaving onSave={vi.fn()} />);
    for (const r of screen.getAllByRole('radio')) expect(r).toHaveAttribute('aria-disabled', 'true');
    expect(screen.getByLabelText('Notatka')).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Zapisywanie…' })).toHaveAttribute('aria-disabled', 'true');
  });

  it('shows the API error and the saved confirmation', () => {
    const { rerender } = render(
      <StatusEditor {...base} error={{ message: 'serwer odrzucił tę wartość.', detail: 'invalid status' }} onSave={vi.fn()} />,
    );
    expect(screen.getByRole('alert')).toHaveTextContent('Nie udało się zapisać zmiany: serwer odrzucił tę wartość.');
    expect(screen.getByText('Odpowiedź serwera:')).toBeInTheDocument();
    expect(screen.getByText('invalid status')).toHaveAttribute('lang', 'en');
    rerender(<StatusEditor {...base} status="in_review" saved onSave={vi.fn()} />);
    expect(screen.getByRole('status')).toHaveTextContent('Zapisano. Status: W analizie.');
  });

  it('submits with the keyboard (form submit)', () => {
    const onSave = vi.fn();
    render(<StatusEditor {...base} onSave={onSave} />);
    choose('W analizie');
    fireEvent.submit(screen.getByRole('form', { name: 'Zmiana statusu' }));
    expect(onSave).toHaveBeenCalledWith({ status: 'in_review' });
  });

  it('does nothing on submit without a change, and shows no confirmation before a save', () => {
    const onSave = vi.fn();
    render(<StatusEditor {...base} onSave={onSave} />);
    fireEvent.submit(screen.getByRole('form', { name: 'Zmiana statusu' }));
    expect(onSave).not.toHaveBeenCalled();
    expect(screen.getByRole('status')).toHaveTextContent(/^$/);
  });

  it('ignores a submit while saving', () => {
    const onSave = vi.fn();
    const { rerender } = render(<StatusEditor {...base} onSave={onSave} />);
    choose('Zamknięte');
    rerender(<StatusEditor {...base} isSaving onSave={onSave} />);
    fireEvent.submit(screen.getByRole('form', { name: 'Zmiana statusu' }));
    expect(onSave).not.toHaveBeenCalled();
  });

  it('new saved values reset the form in place: same nodes, focus kept, live region announced', () => {
    const onSave = vi.fn();
    const { rerender } = render(<StatusEditor {...base} onSave={onSave} />);
    const radio = screen.getByRole('radio', { name: 'Potwierdzone' });
    const save = screen.getByRole('button', { name: 'Zapisz decyzję' });
    const live = screen.getByRole('status');
    expect(live).toHaveTextContent(/^$/);
    choose('Potwierdzone');
    save.focus();
    rerender(<StatusEditor {...base} status="confirmed" note="ok" saved onSave={onSave} />);
    expect(screen.getByRole('radio', { name: 'Potwierdzone' })).toBe(radio);
    expect(radio).toBeChecked();
    expect(screen.getByLabelText('Notatka')).toHaveValue('ok');
    expect(screen.getByRole('button', { name: 'Zapisz decyzję' })).toBe(save);
    expect(save).toHaveFocus();
    expect(screen.getByRole('status')).toBe(live);
    expect(live).toHaveTextContent('Zapisano. Status: Potwierdzone.');
  });

  it('does not change the choice while saving', () => {
    render(<StatusEditor {...base} isSaving onSave={vi.fn()} />);
    choose('Zamknięte');
    expect(screen.getByRole('radio', { name: 'Nowe' })).toBeChecked();
  });
});

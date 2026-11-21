import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { StatusEditor } from './StatusEditor';

const base = { status: 'new' as const, note: null, isSaving: false, error: undefined, saved: false };

describe('StatusEditor', () => {
  it('offers all five statuses and starts at the saved one', () => {
    render(<StatusEditor {...base} onSave={vi.fn()} />);
    const select = screen.getByLabelText('Status');
    expect(select).toHaveValue('new');
    expect(Array.from((select as HTMLSelectElement).options).map((o) => o.value)).toEqual([
      'new',
      'in_review',
      'confirmed',
      'false_positive',
      'closed',
    ]);
  });

  it('saves the chosen status and note', () => {
    const onSave = vi.fn();
    render(<StatusEditor {...base} onSave={onSave} />);
    const save = screen.getByRole('button', { name: 'Zapisz' });
    expect(save).toHaveAttribute('aria-disabled', 'true');
    fireEvent.change(screen.getByLabelText('Status'), { target: { value: 'confirmed' } });
    fireEvent.change(screen.getByLabelText('Notatka'), { target: { value: 'Potwierdzone ręcznie' } });
    expect(save).toHaveAttribute('aria-disabled', 'false');
    fireEvent.click(save);
    expect(onSave).toHaveBeenCalledWith({ status: 'confirmed', note: 'Potwierdzone ręcznie' });
  });

  it('sends only the note when the status is unchanged, and an emptied note as null', () => {
    const onSave = vi.fn();
    render(<StatusEditor {...base} note="stara" onSave={onSave} />);
    fireEvent.change(screen.getByLabelText('Notatka'), { target: { value: '  ' } });
    fireEvent.click(screen.getByRole('button', { name: 'Zapisz' }));
    expect(onSave).toHaveBeenCalledWith({ note: null });
  });

  it('sends only the status when the note is unchanged', () => {
    const onSave = vi.fn();
    render(<StatusEditor {...base} note="n" onSave={onSave} />);
    fireEvent.change(screen.getByLabelText('Status'), { target: { value: 'closed' } });
    fireEvent.click(screen.getByRole('button', { name: 'Zapisz' }));
    expect(onSave).toHaveBeenCalledWith({ status: 'closed' });
  });

  it('disables the controls while saving', () => {
    render(<StatusEditor {...base} isSaving onSave={vi.fn()} />);
    expect(screen.getByLabelText('Status')).toBeDisabled();
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
    rerender(<StatusEditor {...base} saved onSave={vi.fn()} />);
    expect(screen.getByRole('status')).toHaveTextContent('Zapisano.');
  });

  it('submits with the keyboard (form submit)', () => {
    const onSave = vi.fn();
    render(<StatusEditor {...base} onSave={onSave} />);
    fireEvent.change(screen.getByLabelText('Status'), { target: { value: 'in_review' } });
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
    fireEvent.change(screen.getByLabelText('Status'), { target: { value: 'closed' } });
    rerender(<StatusEditor {...base} isSaving onSave={onSave} />);
    fireEvent.submit(screen.getByRole('form', { name: 'Zmiana statusu' }));
    expect(onSave).not.toHaveBeenCalled();
  });

  it('new saved values reset the form in place: same nodes, focus kept, live region announced', () => {
    const onSave = vi.fn();
    const { rerender } = render(<StatusEditor {...base} onSave={onSave} />);
    const select = screen.getByLabelText('Status');
    const save = screen.getByRole('button', { name: 'Zapisz' });
    const live = screen.getByRole('status');
    expect(live).toHaveTextContent(/^$/);
    fireEvent.change(select, { target: { value: 'confirmed' } });
    save.focus();
    rerender(<StatusEditor {...base} status="confirmed" note="ok" saved onSave={onSave} />);
    expect(screen.getByLabelText('Status')).toBe(select);
    expect(select).toHaveValue('confirmed');
    expect(screen.getByLabelText('Notatka')).toHaveValue('ok');
    expect(screen.getByRole('button', { name: 'Zapisz' })).toBe(save);
    expect(save).toHaveFocus();
    expect(screen.getByRole('status')).toBe(live);
    expect(live).toHaveTextContent('Zapisano.');
  });
});

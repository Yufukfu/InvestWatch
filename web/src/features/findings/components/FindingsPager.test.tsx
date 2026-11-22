import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { FindingsPager } from './FindingsPager';

describe('FindingsPager', () => {
  it('shows the page position and moves between pages', () => {
    const onPage = vi.fn();
    render(<FindingsPager page={2} pageSize={10} total={35} onPage={onPage} onPageSize={vi.fn()} />);
    expect(screen.getByText('Strona 2 z 4')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Następna strona' }));
    expect(onPage).toHaveBeenLastCalledWith(3);
    fireEvent.click(screen.getByRole('button', { name: 'Poprzednia strona' }));
    expect(onPage).toHaveBeenLastCalledWith(1);
  });

  it('also carries the short "page / pages" position for the phone, hidden from assistive technology', () => {
    render(<FindingsPager page={1} pageSize={10} total={80} onPage={vi.fn()} onPageSize={vi.fn()} />);
    const short = screen.getByText('1 / 8');
    expect(short).toHaveAttribute('aria-hidden', 'true');
    expect(screen.getByText('Strona 1 z 8')).not.toHaveAttribute('aria-hidden');
  });

  it('disables previous on the first and next on the last page', () => {
    const { rerender } = render(<FindingsPager page={1} pageSize={10} total={20} onPage={vi.fn()} onPageSize={vi.fn()} />);
    expect(screen.getByRole('button', { name: 'Poprzednia strona' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Następna strona' })).toBeEnabled();
    rerender(<FindingsPager page={2} pageSize={10} total={20} onPage={vi.fn()} onPageSize={vi.fn()} />);
    expect(screen.getByRole('button', { name: 'Następna strona' })).toBeDisabled();
  });

  it('changes the page size', () => {
    const onPageSize = vi.fn();
    render(<FindingsPager page={1} pageSize={25} total={9} onPage={vi.fn()} onPageSize={onPageSize} />);
    fireEvent.change(screen.getByLabelText('Na stronie'), { target: { value: '50' } });
    expect(onPageSize).toHaveBeenCalledWith(50);
  });

  it('shows one page when there are no results', () => {
    render(<FindingsPager page={1} pageSize={25} total={0} onPage={vi.fn()} onPageSize={vi.fn()} />);
    expect(screen.getByText('Strona 1 z 1')).toBeInTheDocument();
  });
});

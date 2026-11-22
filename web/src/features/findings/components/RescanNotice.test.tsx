import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { RescanNotice } from './RescanNotice';

const ID = '7c9e6679-7425-40de-944b-e07fc1f90ae7';

describe('RescanNotice', () => {
  it('shows "Zmieniona" with the newer document id and the check time in UTC', () => {
    const { container } = render(<RescanNotice rescan={{ state: 'changed', latestDocumentId: ID, checkedAt: '2026-11-22T06:05:00Z' }} />);
    const badge = screen.getByText('Zmieniona');
    expect(badge).toHaveClass('rescan-badge');
    const line = container.querySelector('.rescan')!;
    expect(line).toHaveClass('rescan-changed');
    expect(line).toHaveTextContent('Strona zmieniła się od tego zgłoszenia');
    expect(line).toHaveTextContent(`Nowsza wersja: dokument ${ID}`);
    expect(line).toHaveTextContent('Sprawdzono: 22.11.2026, 06:05 UTC');
    expect(screen.queryByText('Usunięta')).toBeNull();
  });

  it('shows "Zmieniona" without an id or time when they are absent', () => {
    const { container } = render(<RescanNotice rescan={{ state: 'changed' }} />);
    expect(screen.getByText('Zmieniona')).toBeInTheDocument();
    const line = container.querySelector('.rescan')!;
    expect(line).not.toHaveTextContent('Nowsza wersja: dokument');
    expect(line).not.toHaveTextContent('Sprawdzono');
  });

  it('shows "Usunięta" with a line that the page was removed', () => {
    const { container } = render(<RescanNotice rescan={{ state: 'removed', checkedAt: '2026-11-22T06:05:00Z' }} />);
    expect(screen.getByText('Usunięta')).toHaveClass('rescan-badge');
    const line = container.querySelector('.rescan')!;
    expect(line).toHaveClass('rescan-removed');
    expect(line).toHaveTextContent('Strona została usunięta po tym zgłoszeniu');
    expect(line).toHaveTextContent('Sprawdzono: 22.11.2026, 06:05 UTC');
    expect(line).not.toHaveTextContent('Nowsza wersja');
    expect(screen.queryByText('Zmieniona')).toBeNull();
  });

  it('renders nothing without a re-scan state', () => {
    const { container } = render(<RescanNotice rescan={undefined} />);
    expect(container).toBeEmptyDOMElement();
  });
});

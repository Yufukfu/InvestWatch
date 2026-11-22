import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { ConnectionBanner } from './ConnectionBanner';

describe('ConnectionBanner', () => {
  it('says the live connection is lost, and retries on request', () => {
    const onRetry = vi.fn();
    render(<ConnectionBanner connection="offline" onRetry={onRetry} />);
    expect(screen.getByRole('status')).toHaveTextContent(
      'Brak połączenia na żywo. Alerty mogą się opóźniać; dane odświeżą się po ponownym połączeniu.',
    );
    fireEvent.click(screen.getByRole('button', { name: 'Spróbuj ponownie' }));
    expect(onRetry).toHaveBeenCalledTimes(1);
  });

  it.each(['connecting', 'live'] as const)('shows nothing while %s', (connection) => {
    const { container } = render(<ConnectionBanner connection={connection} onRetry={vi.fn()} />);
    expect(container).toBeEmptyDOMElement();
  });
});

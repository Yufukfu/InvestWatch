import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { LiveBadge } from './LiveBadge';

describe('LiveBadge', () => {
  it.each([
    ['connecting', 'Łączenie…', 'live-connecting'],
    ['live', 'Na żywo', 'live-live'],
    ['offline', 'Brak połączenia na żywo', 'live-offline'],
  ] as const)('shows %s as text', (state, text, cls) => {
    render(<LiveBadge connection={state} />);
    expect(screen.getByText(text)).toHaveClass('live', cls);
  });
});

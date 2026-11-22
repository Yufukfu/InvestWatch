import { render, screen, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { storeWrapper } from '../../test/store';
import { AdvertisersPage } from './AdvertisersPage';

describe('AdvertisersPage', () => {
  it('shows the M1 advertisers of the contract mock and no M3 advertiser', async () => {
    render(<AdvertisersPage />, { wrapper: storeWrapper() });
    expect(screen.getByRole('heading', { name: 'Reklamodawcy i promowane firmy (M1)' })).toBeInTheDocument();
    const table = await screen.findByRole('table');
    for (const name of ['Jan Inwestor', 'Marek Trader', 'Finanse z Kasią', 'Ekonomia na luzie'])
      expect(within(table).getByText(name)).toBeInTheDocument();
    expect(within(table).queryByText('Sygnały VIP')).toBeNull();
    expect(within(table).getAllByText('Alfa Inwestycje Dom Maklerski S.A.')).toHaveLength(2);
  });
});

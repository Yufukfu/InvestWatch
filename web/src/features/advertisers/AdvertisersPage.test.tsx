import { act, fireEvent, render, screen, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { storeWrapper } from '../../test/store';
import { AdvertisersPage } from './AdvertisersPage';

const ALFA = 'facc6bd1-c728-5348-90a4-011b0972fea9';
const MAREK_ID = 'ef85ced1-2f04-5f3d-bc93-63a276c206fd';
const MAREK_TITLE = 'Finfluencer @marek_trader reklamuje Alfa Inwestycje DM z kodem polecającym';

function renderPage(search = '') {
  window.history.replaceState(null, '', `/${search}#powiazania`);
  return render(<AdvertisersPage />, { wrapper: storeWrapper() });
}

const figures = () => document.querySelector('.adv-figures');

describe('AdvertisersPage (contract mock)', () => {
  it('states the KPI sentence and draws the M1 advertisers, none from M3', async () => {
    renderPage();
    await screen.findByRole('img', { name: /Graf powiązań/ });
    expect(figures()).toHaveTextContent('3 reklamodawcy promują 2 licencjonowane firmy, w tym 0 powtarzających się');
    const left = screen.getByRole('list', { name: 'Reklamodawcy' });
    expect(within(left).getAllByRole('listitem').map((li) => li.textContent)).toEqual(['@finanse_z_kasia1', '@inwestor_jan1', '@marek_trader1']);
    expect(screen.queryByText('Sygnały VIP')).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: 'Tabela' }));
    const table = screen.getByRole('table');
    for (const name of ['Jan Inwestor', 'Marek Trader', 'Finanse z Kasią', 'Ekonomia na luzie']) expect(within(table).getByText(name)).toBeInTheDocument();
    expect(within(table).getAllByText('Alfa Inwestycje Dom Maklerski S.A.')).toHaveLength(2);
  });

  it('highlights the top advertiser of the side table until another row is picked', async () => {
    renderPage();
    await screen.findByRole('img', { name: /Graf powiązań/ });
    expect(screen.getByRole('button', { name: '@finanse_z_kasia' })).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByRole('link', { name: 'Zobacz zgłoszenia @finanse_z_kasia' })).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: '@marek_trader' }));
    expect(screen.getByRole('button', { name: '@marek_trader' })).toHaveAttribute('aria-pressed', 'true');
    expect(document.querySelector('[data-edge^="h:@marek_trader|"]')).toHaveClass('adv-edge-selected');
  });

  it('lists in the side table only advertisers with a matched firm, like the graph', async () => {
    renderPage();
    await screen.findByRole('img', { name: /Graf powiązań/ });
    // @ekonomia_na_luzie has only findings with no matched firm: it stays in the Tabela view, not in the side table.
    expect(screen.queryByRole('button', { name: '@ekonomia_na_luzie' })).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: 'Tabela' }));
    expect(within(screen.getByRole('table')).getByText('Ekonomia na luzie')).toBeInTheDocument();
  });

  it('applies the filters to the loaded findings', async () => {
    renderPage();
    await screen.findByRole('img', { name: /Graf powiązań/ });
    fireEvent.change(screen.getByLabelText('Ryzyko'), { target: { value: 'low' } });
    expect(figures()).toHaveTextContent('0 reklamodawców promuje 0 licencjonowanych firm, w tym 0 powtarzających się');
    fireEvent.change(screen.getByLabelText('Ryzyko'), { target: { value: 'all' } });
    fireEvent.click(screen.getByLabelText('Tylko powtarzający się'));
    expect(screen.getByRole('status')).toHaveTextContent('Brak reklamodawców dla wybranych filtrów');
  });

  it('opens a relation from an edge, keeps it in the URL and goes back to the graph', async () => {
    const { container } = renderPage();
    await screen.findByRole('img', { name: /Graf powiązań/ });
    fireEvent.click(container.querySelector(`[data-edge="h:@marek_trader|${ALFA}"]`)!);
    const p = new URLSearchParams(window.location.search);
    expect(p.get('rel_adv')).toBe('h:@marek_trader');
    expect(p.get('rel_firm')).toBe(ALFA);
    expect(window.location.hash).toBe('#powiazania');
    expect(screen.getByRole('heading', { level: 2 })).toHaveTextContent('1 zgłoszenie: @marek_trader → promuje Alfa Inwestycje Dom Maklerski S.A.');
    expect(screen.getByRole('button', { name: MAREK_TITLE })).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Powiązania' }));
    expect(window.location.search).toBe('');
    expect(screen.getByRole('img', { name: /Graf powiązań/ })).toBeInTheDocument();
  });

  it('reopens a relation from a shared link and follows the browser back button', async () => {
    renderPage(`?rel_adv=${encodeURIComponent('h:@marek_trader')}&rel_firm=${ALFA}`);
    expect(await screen.findByText('WYBRANA RELACJA')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('link', { name: 'Pokaż cały profil reklamodawcy' }));
    expect(screen.getByText('WYBRANY REKLAMODAWCA')).toBeInTheDocument();
    expect(new URLSearchParams(window.location.search).has('rel_firm')).toBe(false);
    act(() => {
      window.history.replaceState(null, '', '/#powiazania');
      window.dispatchEvent(new PopStateEvent('popstate'));
    });
    expect(screen.getByRole('img', { name: /Graf powiązań/ })).toBeInTheDocument();
  });

  it('opens a finding of the relation on the findings page', async () => {
    renderPage(`?rel_adv=${encodeURIComponent('h:@marek_trader')}`);
    fireEvent.click(await screen.findByRole('button', { name: MAREK_TITLE }));
    const p = new URLSearchParams(window.location.search);
    expect(p.get('finding')).toBe(MAREK_ID);
    expect(p.has('rel_adv')).toBe(false);
    expect(window.location.hash).toBe('#zgloszenia');
  });
});

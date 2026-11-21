import { render, screen } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { describe, expect, it } from 'vitest';
import findings from '../../mocks/fixtures/findings.json';
import { server } from '../../test/setup';
import { storeWrapper } from '../../test/store';
import { FindingsPage } from './FindingsPage';

describe('FindingsPage', () => {
  it('shows the loading text, then the rows from the API', async () => {
    render(<FindingsPage />, { wrapper: storeWrapper() });
    expect(screen.getByText('Ładowanie…')).toBeInTheDocument();
    expect(await screen.findByText(findings.items[0].title)).toBeInTheDocument();
    expect(screen.getAllByRole('row')).toHaveLength(findings.items.length + 1);
  });

  it('shows the error alert when the request fails', async () => {
    server.use(http.get('http://localhost/api/findings', () => HttpResponse.error()));
    render(<FindingsPage />, { wrapper: storeWrapper() });
    expect(await screen.findByRole('alert')).toHaveTextContent('Nie udało się pobrać zgłoszeń.');
    expect(screen.queryByText('Ładowanie…')).toBeNull();
  });
});

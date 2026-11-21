import { render, screen } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { describe, expect, it } from 'vitest';
import { server } from '../../test/setup';
import { storeWrapper } from '../../test/store';
import { HealthPage } from './HealthPage';

describe('HealthPage', () => {
  it('shows the checking state, then the status from the API', async () => {
    render(<HealthPage />, { wrapper: storeWrapper() });
    expect(screen.getByRole('status')).toHaveTextContent('Sprawdzanie…');
    expect(await screen.findByText('System działa')).toBeInTheDocument();
  });

  it('shows the API-down state when the request fails', async () => {
    server.use(http.get('http://localhost/api/health', () => HttpResponse.error()));
    render(<HealthPage />, { wrapper: storeWrapper() });
    expect(await screen.findByText('Brak połączenia z API')).toBeInTheDocument();
  });
});

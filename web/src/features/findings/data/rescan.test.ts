import { describe, expect, it } from 'vitest';
import { parseRescan } from './rescan';

const ID = '7c9e6679-7425-40de-944b-e07fc1f90ae7';
const AT = '2026-11-22T06:00:00Z';

describe('parseRescan', () => {
  it('keeps a changed state with its newer document id and check time', () => {
    expect(parseRescan({ scraper: 'httpx', rescan: { state: 'changed', latest_document_id: ID, checked_at: AT } })).toEqual({
      state: 'changed',
      latestDocumentId: ID,
      checkedAt: AT,
    });
  });

  it('keeps a removed state without a document id', () => {
    expect(parseRescan({ rescan: { state: 'removed', latest_document_id: null, checked_at: AT } })).toEqual({ state: 'removed', checkedAt: AT });
  });

  it('shows nothing for current, a missing key or no scrape_meta', () => {
    expect(parseRescan({ rescan: { state: 'current', latest_document_id: null, checked_at: AT } })).toBeUndefined();
    expect(parseRescan({ scraper: 'playwright' })).toBeUndefined();
    expect(parseRescan(undefined)).toBeUndefined();
    expect(parseRescan(null)).toBeUndefined();
  });

  it('treats an unknown state or a non-object rescan as no state', () => {
    expect(parseRescan({ rescan: { state: 'gone', checked_at: AT } })).toBeUndefined();
    expect(parseRescan({ rescan: { state: 'CHANGED' } })).toBeUndefined();
    expect(parseRescan({ rescan: 'changed' })).toBeUndefined();
    expect(parseRescan({ rescan: ['changed'] })).toBeUndefined();
    expect(parseRescan({ rescan: null })).toBeUndefined();
    expect(parseRescan('rescan')).toBeUndefined();
    expect(parseRescan({ rescan: { state: 'toString' } })).toBeUndefined();
  });

  it('drops an id that is not a UUID and a time that does not parse', () => {
    expect(parseRescan({ rescan: { state: 'changed', latest_document_id: '<img src=x onerror=alert(1)>', checked_at: 'yesterday' } })).toEqual({
      state: 'changed',
    });
    expect(parseRescan({ rescan: { state: 'changed', latest_document_id: `${ID}x`, checked_at: 42 } })).toEqual({ state: 'changed' });
    expect(parseRescan({ rescan: { state: 'changed', latest_document_id: `x${ID}` } })).toEqual({ state: 'changed' });
    expect(parseRescan({ rescan: { state: 'changed', latest_document_id: 123 } })).toEqual({ state: 'changed' });
    expect(parseRescan({ rescan: { state: 'changed', latest_document_id: [ID] } })).toEqual({ state: 'changed' });
  });
});

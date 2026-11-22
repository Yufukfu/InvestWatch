# Follow-ups

| Finding | Disposition |
|---|---|
| PR 108 review comment 2: the scraper stores `source.url` in `job_errors.url`, while the api matches `job_errors.url IN {canonical_url or url, document.url}` and `documents.url` is the final URL after redirects, so a source that redirects (http to https, a missing trailing slash) never shows as removed; redaction can also change the URL. The scraper cannot store the right URL cheaply: `FetchFailure` does not carry the final URL of a 404, only `FetchResult` does. Proposed for Damian: match removal rows by `source_id` alone (a web source is one page and the scraper's own lookup is per `source_id`). | new-item (api, Damian) |

# Design

## Context

See proposal.md. The detail is mounted per `finding=<id>` (`FindingsPage` keys `DetailContainer` on the id), loaded by `useFindingDetail` through the generated `useGetFindingsByIdQuery`. Components take props only (ADR 0204). `web/` calls the API only through the client generated from the committed `openapi.json` snapshot (ADR 0201, `web/README.md`).

## Goals / Non-Goals

**Goals:** combine module results in the detail without changing per-finding status semantics.

**Non-Goals:** a document-grouped list (paging is per finding on the API, so groups would break across pages), and any web-side workaround for the missing parameter.

## Decisions

1. **Combine in the detail, not the list.** The API pages findings, not documents. A list grouped by document would split one post across pages or need a new endpoint. The detail already holds the shared material (excerpt, screenshot), so it is the natural "unified object". Rejected alternative: page-local "same document" labels in the table. They are silently incomplete when the sibling falls on another page.
2. **The switcher changes `finding=<id>`, it is not local state.** The URL model, deep links, back button and the per-id remount stay as they are. Focus is moved to the switcher button of the new finding after the remount, so keyboard users don't lose their place.
3. **The sibling request is a separate hook (`useDocumentFindings(documentId)`) on the generated list query** with `document_id` and `page_size` 10 (at most 3 modules exist). It is independent of the list filters, so a module filter does not hide siblings. Its failure only hides the switcher.
4. **Wait for the contract, no stopgap.** Before the parameter exists, task group 1 ships alone (host and model). Group 2 starts after Damian's contract PR merges: regenerate `web/src/api/openapi.json` and the client, then build the switcher. A hand-written request or a `q` search hack would break ADR 0201.

## Risks / Trade-offs

- [Damian's parameter lands late or with another name] → Group 2 is the only part that depends on it. Group 1 ships on its own with `Refs #33`.
- [The mock server ignores unknown query params and returns every finding] → The hook filters the response by `document_id` again on the client, so the switcher never shows other documents' findings.
- [Remount on switch resets the scroll of the panel] → This is acceptable, because the module part changes completely anyway.

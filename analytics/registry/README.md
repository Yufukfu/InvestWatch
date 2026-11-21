# Fictional firms

`seed.csv` holds fictional firms: the three used by `contracts/mocks/`, with the same `registry_id`s, so CLI output lines up with the dashboard mocks, and one foreign firm without a Polish branch (`foreign_no_branch`) for the M1 Polish-targeting tests. It is not the real KNF register. Columns: `id, name, aliases, type, country, website_domains, source_url`; list fields are separated by `|`. Point `REGISTRY_CSV` at another file to use a different registry.

A registry in which no firm has a `source_url` is treated as demonstration data (`Registry.demo`): M3 findings then say the entity was not found in the loaded registry "(dane demonstracyjne)". The real KNF loader sets `source_url` (the KNF register page) on every firm, which removes that note.

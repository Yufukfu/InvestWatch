## MODIFIED Requirements

### Requirement: Preprocessing
Analytics SHALL normalize text (NFKC, collapsed whitespace) for matching, language guess and excerpts, and split it into sentences. It SHALL use the stored `content_hash` as is and SHALL NOT compute one. Evidence quotes SHALL be exact substrings of the original `text`. Legal forms, titles and `<year> r.` SHALL NOT end a sentence; abbreviations that are also ordinary words (`ok.`, `tel.`, `art.` and similar) SHALL end one unless a digit follows, directly or after an opening bracket or quote.

#### Scenario: Equivalent texts hash the same
- **WHEN** two documents differ only in whitespace runs or Unicode composition and carry the stored `content_hash` (NFC, `.docs/integration-plan.md` §3)
- **THEN** analytics sees equal `content_hash` values, because it passes the stored values through instead of hashing its NFKC text

#### Scenario: Stored content hash is used as is
- **WHEN** a document whose text holds compatibility characters (`ﬁ`, `²`) is loaded with a stored `content_hash`
- **THEN** the loaded document carries that exact value and preprocessing produces no hash of its own

#### Scenario: Document without a stored hash
- **WHEN** a document has no `content_hash`
- **THEN** it is analysed as usual and analytics does not fill one in

#### Scenario: Matching folds compatibility characters
- **WHEN** the text contains `ﬁ` or full-width digits
- **THEN** the normalized text used for matching holds `fi` and ASCII digits, while the original `text` is unchanged

#### Scenario: Sentence split keeps legal forms
- **WHEN** the text is `Reklama. Bank Przykładowy S.A. – Biuro Maklerskie. Otwórz IKE.`
- **THEN** it splits into three sentences and `S.A.` does not end a sentence

#### Scenario: Ordinary word that is also an abbreviation
- **WHEN** the text is `Wszystko jest ok. Zysk 15% rocznie.`
- **THEN** it splits into two sentences, while `Zysk wynosi ok. 15% rocznie.` stays one

#### Scenario: Language guess
- **WHEN** the text is Polish marketing copy, and separately an English risk warning
- **THEN** the guesses are `pl` and `en`

#### Scenario: Empty text
- **WHEN** `text` is empty or whitespace only
- **THEN** the pipeline returns no findings and logs the reason `empty_text`

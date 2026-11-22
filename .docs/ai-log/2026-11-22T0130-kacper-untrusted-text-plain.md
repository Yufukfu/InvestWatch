---
when: Sun ~01:30
who: Kacper
---

## What was done with AI

A Claude Code subagent took issue #54 (R55 of `analytics-llm-p0`): audited every `web/` component that renders model or scraped finding text, wrote a hostile-finding test first (`<img onerror>`, Markdown `javascript:` link, bare URL, U+202E), then put each value alone in a `dir="auto"` element; scripted mutation check and an `iw-reviewer` pass

## Outcome / lesson

Change `untrusted-text-plain`. The audit found no HTML, Markdown or auto-linking path (React text everywhere, `react/no-danger` on); the real gap was bidi: U+202E could reorder the closing quote and the ` – ` separator. jsdom has no layout, so the test pins the structure (each U+202E directly in a `dir="auto"` element holding only that value) instead of rendered order. One mutant survived and was equivalent (an extra outer `dir`); it was replaced by the meaningful variant. `iw-commit-cycle` says no `Co-Authored-By` while the session brief asked for one; the repo rule was followed

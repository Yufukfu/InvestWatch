# Follow-ups

From @hen68's review of PR #91.

| Item | Disposition |
|---|---|
| The toast `aria-label`s (`AlertToasts.tsx`) and the live-region announcement (`useRealtime.ts`) put the alert title into a string with no bidi isolation (screen-reader text; the title is capped and trimmed). | `new-item`: issue #99. |
| `StatusEditor.tsx` shows the server's `error.detail` after a UI label, with no `dir`. | `new-item`: issue #99. |
| `firm.name` and `rule.name` are not isolated. | `wont-fix`: neither is scraped or model text. `firm.name` is the matched entry of our firm registry (`registry_csv`, `match.firm.name` in analytics `modules/m1.py` and `m2.py`) and sits alone in its `<p>`; `rule.name` comes from the rule catalogue `m2_rules.yaml`. |

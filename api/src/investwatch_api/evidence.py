"""Evidence pack of one finding (GET /findings/{id}/export, issue #70): a read-only case file for UKNF follow-up.

The pack is the finding detail plus the raw HTML from object storage (`documents.html_object_key`, never a key from
the request) with its SHA-256, and the failed rules pulled out. `render_html` turns it into a printable page in
Polish. Every value on that page comes from scraped content or the analytics output, so all of it is escaped and
only http(s) URLs become links; the response headers forbid scripts entirely.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from html import escape
from typing import Literal
from urllib.parse import quote, urlsplit

from .db.mapping import format_time
from .objectstore import ObjectStore, ObjectStoreError

ExportFormat = Literal["json", "html"]
EXPORT_VERSION = "1"
RAW_LIMIT = 2_000_000  # bytes of raw HTML carried in the pack; the hash always covers the whole object
HTML_HEADERS = {
    "Content-Security-Policy": ("default-src 'none'; img-src 'self'; style-src 'unsafe-inline'; base-uri 'none'; "
                                "form-action 'none'; frame-ancestors 'none'"),
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
}


async def _raw(document: dict | None, objects: ObjectStore) -> dict:
    key = (document or {}).get("html_object_key")
    out = {"object_key": key if isinstance(key, str) and key else None, "available": False,
           "unavailable_reason": None, "sha256": None, "size_bytes": None, "truncated": False, "html": None}
    if out["object_key"] is None:
        return {**out, "unavailable_reason": "no_key"}
    try:
        data = await objects.get(out["object_key"])
    except ObjectStoreError:
        return {**out, "unavailable_reason": "store_down"}
    if data is None:
        return {**out, "unavailable_reason": "not_found"}
    return {**out, "available": True, "sha256": hashlib.sha256(data).hexdigest(), "size_bytes": len(data),
            "truncated": len(data) > RAW_LIMIT, "html": data[:RAW_LIMIT].decode("utf-8", errors="replace")}


async def evidence_pack(detail: dict, objects: ObjectStore) -> dict:
    """The JSON pack from a GET /findings/{id} body. A store outage degrades `raw`, never the whole export."""
    finding = {k: v for k, v in detail.items() if k not in ("document", "screenshot_urls")}
    document = detail.get("document")
    return {
        "export_version": EXPORT_VERSION,
        "generated_at": format_time(datetime.now(timezone.utc).replace(microsecond=0)),
        "finding": finding,
        "document": document,
        "raw": await _raw(document, objects),
        "screenshot_urls": detail.get("screenshot_urls") or {},
        "failed_rules": [r for r in finding.get("rules") or [] if r.get("result") == "fail"],
    }


# --- printable page ------------------------------------------------------------------------------

_RESULT = {"fail": "niespełniona / sygnał wykryty", "pass": "spełniona", "not_applicable": "nie dotyczy",
           "uncertain": "niepewna"}
_SEVERITY = {"high": "wysoka", "medium": "średnia", "low": "niska"}
_RISK = {"high": "wysokie", "medium": "średnie", "low": "niskie"}
_RAW_MISSING = {"no_key": "brak klucza obiektu w dokumencie", "not_found": "obiekt nie istnieje w magazynie",
                "store_down": "magazyn obiektów niedostępny"}


def _e(value) -> str:
    return "—" if value is None or value == "" else escape(str(value), quote=True)


def _link(url) -> str:
    """A clickable link only for http(s); anything else (javascript:, data:) is shown as escaped text."""
    if isinstance(url, str) and urlsplit(url).scheme.lower() in ("http", "https"):
        return f'<a href="{escape(url, quote=True)}" rel="noopener noreferrer">{escape(url)}</a>'
    return _e(url)


def _rows(pairs) -> str:
    return "".join(f"<tr><th>{escape(label)}</th><td>{value}</td></tr>" for label, value in pairs)


def _rule(rule: dict) -> str:
    return (f"<section class='rule'><h3>{_e(rule.get('rule_id'))}: {_e(rule.get('name'))}</h3><table>"
            + _rows([("Wynik", _e(_RESULT.get(rule.get("result"), rule.get("result")))),
                     ("Waga", _e(_SEVERITY.get(rule.get("severity"), rule.get("severity")))),
                     ("Podstawa prawna", _e(rule.get("legal_basis"))),
                     ("Metoda", _e(rule.get("method"))),
                     ("Uzasadnienie", _e(rule.get("explanation")))])
            + "</table>"
            + (f"<blockquote>{_e(rule.get('evidence'))}</blockquote>" if rule.get("evidence") else "")
            + "</section>")


def _shot(viewport: str, url: str) -> str:
    # The URL is built by the API from the document id; the viewport key comes from the stored payload.
    src = "/".join(quote(part, safe="") for part in url.split("/"))
    return (f"<figure><img src=\"{escape(src, quote=True)}\" alt=\"Zrzut ekranu ({_e(viewport)})\">"
            f"<figcaption>{_e(viewport)}</figcaption></figure>")


def render_html(pack: dict) -> str:
    f, doc, raw = pack["finding"], pack["document"] or {}, pack["raw"]
    firm, adv, model = f.get("firm") or {}, f.get("advertiser") or {}, f.get("model") or {}
    other = [r for r in f.get("rules") or [] if r.get("result") != "fail"]
    raw_block = (f"<p>SHA-256: <code>{_e(raw['sha256'])}</code>, {raw['size_bytes']} B"
                 + (" (pokazano pierwsze 2 MB)" if raw["truncated"] else "") + "</p>"
                 f"<details><summary>Pokaż surowy HTML</summary><pre>{escape(raw['html'] or '')}</pre></details>"
                 if raw["available"] else f"<p>Niedostępny: {_e(_RAW_MISSING.get(raw['unavailable_reason']))}.</p>")
    shots = "".join(_shot(vp, url) for vp, url in pack["screenshot_urls"].items()) or "<p>Brak zrzutów ekranu.</p>"
    return f"""<!doctype html>
<html lang="pl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Teczka sprawy: {_e(f.get('title'))}</title>
<style>
body{{font:14px/1.5 system-ui,sans-serif;max-width:960px;margin:24px auto;padding:0 16px;color:#111;background:#fff}}
h1{{font-size:22px}} h2{{font-size:17px;border-bottom:1px solid #ccc;padding-bottom:4px;margin-top:28px}}
h3{{font-size:15px;margin:12px 0 4px}} table{{border-collapse:collapse;width:100%}}
th,td{{text-align:left;vertical-align:top;padding:3px 8px;border-bottom:1px solid #eee}} th{{width:28%;color:#444}}
blockquote{{margin:6px 0;padding:6px 10px;border-left:4px solid #b00;background:#fbf3f3;white-space:pre-wrap}}
pre{{white-space:pre-wrap;word-break:break-all;background:#f6f6f6;padding:8px;font-size:12px}}
img{{max-width:100%;border:1px solid #ccc}} figure{{margin:8px 0}} code{{word-break:break-all}}
.text{{white-space:pre-wrap;background:#f6f6f6;padding:8px}} @media print{{details{{display:none}}}}
</style></head><body>
<h1>Teczka sprawy: {_e(f.get('title'))}</h1>
<p>Wygenerowano {_e(pack['generated_at'])} (UTC) przez InvestWatch. Format eksportu {_e(pack['export_version'])}.</p>
<h2>Ustalenie</h2><table>{_rows([
    ("Identyfikator", _e(f.get('id'))), ("Moduł", _e(f.get('module'))), ("Status", _e(f.get('status'))),
    ("Wynik (score)", _e(f.get('score'))), ("Poziom ryzyka", _e(_RISK.get(f.get('risk_level'), f.get('risk_level')))),
    ("Podsumowanie", _e(f.get('summary'))), ("Firma", _e(firm.get('name'))),
    ("Firma w rejestrze KNF", _e({True: 'tak', False: 'nie'}.get(firm.get('authorized')))),
    ("Ogłoszeniodawca", _e(adv.get('name') or adv.get('handle'))),
    ("Na liście ostrzeżeń KNF", _e({True: 'tak', False: 'nie'}.get(adv.get('on_warning_list')))),
    ("Wykryto", _e(f.get('detected_at'))), ("Notatka analityka", _e(f.get('note'))),
    ("Model", _e(model.get('llm') or 'tylko reguły')), ("Embedder", _e(model.get('embedder'))),
    ("Wersja potoku", _e(model.get('pipeline_version')))])}</table>
<h2>Materiał źródłowy</h2><table>{_rows([
    ("URL", _link(doc.get('url') or f.get('url'))), ("URL kanoniczny", _link(doc.get('canonical_url'))),
    ("Platforma", _e(doc.get('platform') or f.get('platform'))), ("Tytuł strony", _e(doc.get('title'))),
    ("Pobrano (fetched_at)", _e(doc.get('fetched_at'))), ("Opublikowano", _e(doc.get('published_at'))),
    ("Status HTTP", _e(doc.get('http_status'))), ("content_hash", f"<code>{_e(doc.get('content_hash'))}</code>"),
    ("Dokument", _e(doc.get('id'))), ("Obiekt HTML (iw-raw)", f"<code>{_e(raw['object_key'])}</code>")])}</table>
<h2>Naruszone reguły ({len(pack['failed_rules'])})</h2>
{''.join(_rule(r) for r in pack['failed_rules']) or '<p>Brak reguł z wynikiem „niespełniona”.</p>'}
<h2>Zrzuty ekranu</h2>{shots}
<h2>Tekst dokumentu</h2><div class="text">{_e(doc.get('text'))}</div>
<h2>Surowy HTML (iw-raw)</h2>{raw_block}
<h2>Pozostałe reguły ({len(other)})</h2>{''.join(_rule(r) for r in other) or '<p>Brak.</p>'}
</body></html>
"""

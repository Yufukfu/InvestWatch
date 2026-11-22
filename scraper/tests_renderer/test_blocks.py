"""The text blocks of a rendered page (spec page-rendering: "Describe the text blocks", "Say where a block is")."""

import pytest

from iw_renderer.blocks import PLACEMENT_WORDS, clean_text
from iw_renderer.render import RenderRequest, render_viewport

BLOCK_KEYS = {
    "viewport", "text", "tag", "font_size_px", "font_weight", "color", "background_color", "bbox", "visible",
    "in_viewport_on_load", "requires_interaction", "region", "overflow_clipped",
}
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36"


def request_for(server, viewport="desktop", **extra):
    return RenderRequest(
        url=f"http://source.test:{server.port}/", source_host="source.test", viewport=viewport,
        headers=(("user-agent", UA),), ports=(server.port,), **extra,
    )


async def blocks_of(server, browser, address_check, html, viewport="desktop", **extra):
    server.serve("source.test", "/", html)
    result = await render_viewport(browser, request_for(server, viewport, **extra), address_check)
    return result.blocks


def by_text(blocks, text):
    (found,) = [block for block in blocks if block["text"] == text]
    return found


async def test_a_block_has_every_contract_field_and_the_viewport(server, browser, address_check):
    blocks = await blocks_of(server, browser, address_check, "<body style='margin:0'><p>Zysk do 20%</p></body>", "tablet")

    (block,) = blocks
    assert set(block) == BLOCK_KEYS and block["viewport"] == "tablet" and block["tag"] == "p"
    assert block["text"] == "Zysk do 20%" and block["font_weight"] == 400
    assert len(block["bbox"]) == 4 and block["visible"] is True and block["region"] == "main"


async def test_the_font_size_of_each_block_is_reported(server, browser, address_check):
    html = "<p style='font-size:16px'>Oferta</p><p style='font-size:10px'>Ryzyko utraty kapitału</p>"

    blocks = await blocks_of(server, browser, address_check, html)

    assert by_text(blocks, "Oferta")["font_size_px"] == 16 and by_text(blocks, "Ryzyko utraty kapitału")["font_size_px"] == 10


async def test_a_bold_weight_is_an_integer(server, browser, address_check):
    blocks = await blocks_of(server, browser, address_check, "<p style='font-weight:bold'>Mocny</p>")

    assert blocks[0]["font_weight"] == 700 and isinstance(blocks[0]["font_weight"], int)


async def test_script_style_noscript_and_template_text_is_not_a_block(server, browser, address_check):
    html = (
        "<body><style>.a{color:red} /* ryzyko */</style><script>var s='ryzyko';</script><noscript>ryzyko</noscript>"
        "<template><p>ryzyko</p></template><p>Widoczny</p></body>"
    )

    blocks = await blocks_of(server, browser, address_check, html)

    assert [block["text"] for block in blocks] == ["Widoczny"]


async def test_inline_markup_stays_in_the_text_of_its_block_in_document_order(server, browser, address_check):
    html = "<p>Pierwszy <b>akapit</b> tekstu</p><div>Drugi</div><p>Trzeci</p>"

    blocks = await blocks_of(server, browser, address_check, html)

    assert [block["text"] for block in blocks] == ["Pierwszy akapit tekstu", "Drugi", "Trzeci"]


async def test_a_semi_transparent_colour_is_composited_over_its_background(server, browser, address_check):
    html = "<div style='background:#ffffff'><p style='color:rgba(0,0,0,0.25)'>Szary</p></div>"

    block = (await blocks_of(server, browser, address_check, html))[0]

    assert block["color"] == "#bfbfbf" and block["background_color"] == "#ffffff"


async def test_the_nearest_opaque_ancestor_background_is_used(server, browser, address_check):
    html = "<div style='background:#102030'><section><p style='color:#ffffff'>Jasny</p></section></div>"

    block = (await blocks_of(server, browser, address_check, html))[0]

    assert block["background_color"] == "#102030" and block["color"] == "#ffffff"


@pytest.mark.parametrize(
    "background",
    ["background-image:linear-gradient(red,blue)", "background-image:url(data:image/gif;base64,R0lGODlhAQABAAAAACw=)"],
)
async def test_a_background_that_cannot_be_computed_is_null(server, browser, address_check, background):
    html = f"<div style='{background}'><p>Na obrazie</p></div>"

    block = (await blocks_of(server, browser, address_check, html))[0]

    assert block["background_color"] is None


async def test_text_that_is_hidden_is_still_emitted_and_marked_not_visible(server, browser, address_check):
    html = (
        "<p style='display:none'>a</p><p style='visibility:hidden'>b</p><p style='opacity:0'>c</p>"
        "<div style='width:0;height:0;overflow:hidden'><span style='display:block'>d</span></div><p>e</p>"
    )

    blocks = await blocks_of(server, browser, address_check, html)

    assert {block["text"]: block["visible"] for block in blocks} == {"a": False, "b": False, "c": False, "d": False, "e": True}
    assert {block["text"]: block["in_viewport_on_load"] for block in blocks} == {
        "a": False, "b": False, "c": False, "d": False, "e": True,
    }


async def test_a_risk_text_in_a_closed_details_needs_interaction_and_is_not_visible(server, browser, address_check):
    html = "<details><summary>Czytaj</summary><p>Ryzyko utraty</p></details><details open><summary>Otwarte</summary><p>Jawne</p></details>"

    blocks = await blocks_of(server, browser, address_check, html)

    closed, opened = by_text(blocks, "Ryzyko utraty"), by_text(blocks, "Jawne")
    assert (closed["requires_interaction"], closed["visible"]) == (True, False)
    assert (opened["requires_interaction"], opened["visible"]) == (False, True)
    assert by_text(blocks, "Czytaj")["requires_interaction"] is False


async def test_a_panel_controlled_by_a_collapsed_button_needs_interaction(server, browser, address_check):
    html = (
        "<button aria-controls='panel' aria-expanded='false'>Więcej</button>"
        "<div id='panel' style='display:none'><p>Ukryte ostrzeżenie</p></div><p>Jawny</p>"
    )

    blocks = await blocks_of(server, browser, address_check, html)

    assert by_text(blocks, "Ukryte ostrzeżenie")["requires_interaction"] is True
    assert by_text(blocks, "Jawny")["requires_interaction"] is False
    assert by_text(blocks, "Ukryte ostrzeżenie")["visible"] is False


async def test_a_block_below_the_first_viewport_is_not_in_viewport_on_load(server, browser, address_check):
    html = "<body style='margin:0'><p>Na górze</p><div style='height:3000px'></div><p>Na dole</p></body>"

    blocks = await blocks_of(server, browser, address_check, html)

    assert by_text(blocks, "Na górze")["in_viewport_on_load"] is True
    assert by_text(blocks, "Na dole")["in_viewport_on_load"] is False
    assert by_text(blocks, "Na dole")["bbox"][1] > 3000  # relative to the page, not the viewport


async def test_a_block_that_crosses_the_fold_is_not_in_viewport_on_load(server, browser, address_check):
    html = "<body style='margin:0'><div style='height:880px'></div><p style='font-size:40px;margin:0'>Przecina</p></body>"

    block = (await blocks_of(server, browser, address_check, html))[0]

    assert block["in_viewport_on_load"] is False and block["visible"] is True


@pytest.mark.parametrize(
    ("html", "region"),
    [
        ("<footer><div class='legal'><p>Ryzyko</p></div></footer>", "legal"),
        ("<footer><p>Prawa zastrzeżone</p></footer>", "footer"),
        ("<div role='contentinfo'><p>Stopka</p></div>", "footer"),
        ("<header><p>Nagłówek</p></header>", "header"),
        ("<div role='banner'><p>Baner</p></div>", "header"),
        ("<aside><p>Z boku</p></aside>", "aside"),
        ("<div style='position:fixed;bottom:0'><p>Używamy plików cookie</p></div>", "overlay"),
        ("<dialog open><p>Okno</p></dialog>", "overlay"),
        ("<p>Zwykły tekst</p>", "main"),
        ("<main><p>W środku</p></main>", "main"),
        ("<small>Drobny druk</small>", "legal"),
        ("<div role='note'><p>Uwaga</p></div>", "legal"),
        ("<div class='nota-prawna'><p>Nota</p></div>", "legal"),
        ("<div id='Klauzula-Informacyjna'><p>Klauzula</p></div>", "legal"),
        ("<div aria-label='Zastrzeżenia'><p>Etykieta</p></div>", "legal"),
        ("<section><h2>Objaśnienia</h2><p>Pod nagłówkiem</p></section>", "legal"),
        ("<div class='risk-warning'><p>Ryzyko straty</p></div>", "main"),
        ("<div class='ostrzezenie ryzyko'><p>Ostrzeżenie</p></div>", "main"),
    ],
)
async def test_the_region_of_a_block_follows_its_placement(server, browser, address_check, html, region):
    blocks = await blocks_of(server, browser, address_check, html)

    assert [block["region"] for block in blocks if block["tag"] not in ("h2",)][-1] == region


async def test_a_prominent_risk_box_below_the_fold_is_main_not_legal(server, browser, address_check):
    html = "<div style='height:2000px'></div><div class='risk-warning'>Ryzyko</div><div class='nota-prawna'>Nota</div>"

    blocks = await blocks_of(server, browser, address_check, html)

    assert by_text(blocks, "Ryzyko")["region"] == "main" and by_text(blocks, "Nota")["region"] == "legal"


def test_the_placement_words_hold_no_content_words():
    assert not {"risk", "ryzyk", "ostrzezen", "warning"} & set(PLACEMENT_WORDS)
    assert {"legal", "prawn", "regulamin", "disclaimer", "terms"} <= set(PLACEMENT_WORDS)


async def test_the_same_warning_is_a_block_per_viewport_and_clipped_where_it_is_cut(server, browser, address_check):
    html = (
        "<head><meta name='viewport' content='width=device-width'></head>"
        "<body style='margin:0'><div style='overflow:hidden;white-space:nowrap'>"
        "<p style='margin:0'>Ostrzeżenie o ryzyku utraty kapitału jest bardzo długie i nie mieści się w wąskim ekranie</p></div></body>"
    )
    server.serve("source.test", "/", html)

    desktop = await render_viewport(browser, request_for(server, "desktop"), address_check)
    mobile = await render_viewport(browser, request_for(server, "mobile"), address_check)

    assert desktop.blocks[0]["text"] == mobile.blocks[0]["text"]
    assert (desktop.blocks[0]["viewport"], mobile.blocks[0]["viewport"]) == ("desktop", "mobile")
    assert desktop.blocks[0]["overflow_clipped"] is False and mobile.blocks[0]["overflow_clipped"] is True


async def test_the_mobile_blocks_follow_the_viewport_meta_layout(server, browser, address_check):
    html = (
        "<head><meta name='viewport' content='width=device-width'></head>"
        "<body style='margin:0'><p style='width:100%'>Responsywny</p></body>"
    )
    server.serve("source.test", "/", html)

    mobile = await render_viewport(browser, request_for(server, "mobile"), address_check)

    assert mobile.blocks[0]["bbox"][2] <= 390


async def test_more_blocks_than_the_cap_keeps_the_first_in_document_order_and_marks_the_render_truncated(
    server, browser, address_check
):
    html = "".join(f"<p>akapit {n}</p>" for n in range(30))
    server.serve("source.test", "/", html)

    result = await render_viewport(browser, request_for(server, max_blocks=10), address_check)

    assert [block["text"] for block in result.blocks] == [f"akapit {n}" for n in range(10)]
    assert result.truncated is True


async def test_a_page_within_the_caps_is_not_truncated(server, browser, address_check):
    server.serve("source.test", "/", "<p>jeden</p>")

    result = await render_viewport(browser, request_for(server, max_blocks=10), address_check)

    assert result.truncated is False


async def test_a_long_text_is_cut_at_4000_characters_and_marks_the_render_truncated(server, browser, address_check):
    server.serve("source.test", "/", f"<p>{'ą' * 5000}</p>")

    result = await render_viewport(browser, request_for(server), address_check)

    assert result.blocks[0]["text"] == "ą" * 4000 and result.truncated is True


async def test_text_is_taken_verbatim_and_never_interpreted(server, browser, address_check):
    server.serve("source.test", "/", "<p>{{7*7}} &lt;script&gt;alert(1)&lt;/script&gt; ${x}</p>")

    result = await render_viewport(browser, request_for(server), address_check)

    assert result.blocks[0]["text"] == "{{7*7}} <script>alert(1)</script> ${x}"


async def test_a_page_that_forges_the_measurement_helpers_still_yields_contract_shaped_blocks(
    server, browser, address_check
):
    html = (
        "<script>Array.prototype.map=()=>['x'];JSON.stringify=()=>'x';"
        "Object.defineProperty(window,'getComputedStyle',{value:()=>({})});</script><p>Prawdziwy</p>"
    )
    server.serve("source.test", "/", html)

    result = await render_viewport(browser, request_for(server), address_check)

    assert [b["text"] for b in result.blocks] == ["Prawdziwy"] and set(result.blocks[0]) == BLOCK_KEYS


def test_clean_text_drops_nul_and_lone_surrogates_but_keeps_real_text():
    assert clean_text("a\x00b\ud800c d ą😀") == "abc d ą😀"
    assert clean_text("  a \n\t b  ") == "a b"


async def test_a_display_contents_wrapper_does_not_become_the_block(server, browser, address_check):
    blocks = await blocks_of(server, browser, address_check, "<div style='display:contents'>Zawartość</div>")

    assert blocks[0]["visible"] is True and blocks[0]["bbox"][2] > 0


async def test_a_collapsed_button_that_is_itself_hidden_does_not_make_its_panel_need_interaction(
    server, browser, address_check
):
    html = (
        "<button aria-controls='panel' aria-expanded='false' style='display:none'>Więcej</button>"
        "<div id='panel' style='display:none'><p>Ukryte</p></div>"
    )

    blocks = await blocks_of(server, browser, address_check, html)

    assert by_text(blocks, "Ukryte")["requires_interaction"] is False


async def test_a_panel_that_is_visible_needs_no_interaction_even_when_its_button_says_collapsed(
    server, browser, address_check
):
    html = "<button aria-controls='panel' aria-expanded='false'>Więcej</button><div id='panel'><p>Widoczne</p></div>"

    blocks = await blocks_of(server, browser, address_check, html)

    assert by_text(blocks, "Widoczne")["requires_interaction"] is False and by_text(blocks, "Widoczne")["visible"] is True


async def test_a_block_above_the_top_of_the_page_is_not_in_viewport_on_load(server, browser, address_check):
    html = "<p style='position:absolute;top:-60px;margin:0'>Nad stroną</p>"

    block = (await blocks_of(server, browser, address_check, html))[0]

    assert block["visible"] is True and block["in_viewport_on_load"] is False


async def test_an_aria_modal_layer_is_an_overlay(server, browser, address_check):
    blocks = await blocks_of(server, browser, address_check, "<div aria-modal='true'><p>Zgoda</p></div>")

    assert blocks[0]["region"] == "overlay"


async def test_a_page_level_heading_does_not_make_the_whole_page_legal(server, browser, address_check):
    blocks = await blocks_of(server, browser, address_check, "<h1>Warunki oferty</h1><p>Treść oferty</p>")

    assert by_text(blocks, "Treść oferty")["region"] == "main"


async def test_a_child_wider_than_its_clipping_parent_is_clipped(server, browser, address_check):
    html = "<div style='width:100px;overflow:hidden'><p style='width:300px;margin:0'>Szeroki</p></div>"

    block = (await blocks_of(server, browser, address_check, html))[0]

    assert block["overflow_clipped"] is True


async def test_a_block_that_fits_is_not_clipped(server, browser, address_check):
    block = (await blocks_of(server, browser, address_check, "<div style='overflow:hidden'><p>Mieści się</p></div>"))[0]

    assert block["overflow_clipped"] is False


def test_sanitize_fits_a_forged_block_to_the_contract_shape():
    from iw_renderer.blocks import sanitize_block

    block, cut = sanitize_block(
        {
            "text": " tekst\x00 ", "tag": "P", "font_size_px": -3, "font_weight": 5000, "color": "red",
            "background_color": "#GGGGGG", "bbox": [1, 2, 3], "visible": "yes", "in_viewport_on_load": 1,
            "requires_interaction": None, "region": "sidebar", "overflow_clipped": "no",
        },
        "tablet",
    )

    assert cut is False and block == {
        "viewport": "tablet", "text": "tekst", "tag": "p", "font_size_px": 0.0, "font_weight": 1000, "color": None,
        "background_color": None, "bbox": None, "visible": False, "in_viewport_on_load": None,
        "requires_interaction": None, "region": "main", "overflow_clipped": None,
    }


def test_sanitize_drops_blocks_without_usable_text_and_cuts_only_beyond_the_cap():
    from iw_renderer.blocks import MAX_TEXT_CHARS, sanitize_block

    assert sanitize_block({"text": " \x00 "}, "desktop") == (None, False)
    assert sanitize_block({"text": 5}, "desktop") == (None, False)
    assert sanitize_block("x", "desktop") == (None, False)
    exact, cut_exact = sanitize_block({"text": "a" * MAX_TEXT_CHARS}, "desktop")
    over, cut_over = sanitize_block({"text": "a" * (MAX_TEXT_CHARS + 1)}, "desktop")
    assert (len(exact["text"]), cut_exact, len(over["text"]), cut_over) == (MAX_TEXT_CHARS, False, MAX_TEXT_CHARS, True)


async def test_the_block_limit_of_the_renderer_bounds_a_larger_request(server, browser, address_check):
    from iw_renderer.render import Renderer
    from iw_renderer.settings import RenderLimits

    server.serve("source.test", "/", "".join(f"<p>p{n}</p>" for n in range(10)))
    renderer = Renderer(browser, address_check, RenderLimits(max_blocks=3))

    result = await renderer.render(request_for(server, max_blocks=100))

    assert len(result.blocks) == 3 and result.truncated is True


def test_the_block_limit_comes_from_the_environment(monkeypatch):
    from iw_renderer.settings import RenderLimits

    monkeypatch.setenv("RENDER_MAX_BLOCKS", "42")
    assert RenderLimits.from_env().max_blocks == 42
    monkeypatch.setenv("RENDER_MAX_BLOCKS", "0")
    with pytest.raises(ValueError, match="RENDER_MAX_BLOCKS"):
        RenderLimits.from_env()


async def test_a_footer_inside_a_header_is_a_footer(server, browser, address_check):
    blocks = await blocks_of(server, browser, address_check, "<header><div role='contentinfo'><p>Stopka</p></div></header>")

    assert blocks[0]["region"] == "footer"


async def test_text_cut_by_its_own_height_is_clipped(server, browser, address_check):
    html = "<p style='width:100px;height:20px;overflow:hidden;margin:0'>bardzo długi tekst który zawija się w wiele linii</p>"

    block = (await blocks_of(server, browser, address_check, html))[0]

    assert block["overflow_clipped"] is True


def test_a_bbox_with_a_non_number_is_dropped():
    from iw_renderer.blocks import sanitize_block

    block, _ = sanitize_block({"text": "x", "bbox": [1, 2, "x", 4]}, "desktop")

    assert block["bbox"] is None


class FakeSession:
    def __init__(self, blocks):
        self.blocks = blocks

    async def send(self, method, params=None):
        if method == "Page.getFrameTree":
            return {"frameTree": {"frame": {"id": "f"}}}
        if method == "Page.createIsolatedWorld":
            return {"executionContextId": 1}
        return {"result": {"value": {"blocks": self.blocks, "truncated": False}}}


async def test_more_blocks_than_the_cap_from_the_page_are_cut_and_flagged_even_if_the_page_did_not_say_so():
    from iw_renderer.blocks import measure_blocks

    measured = await measure_blocks(FakeSession([{"text": f"t{n}"} for n in range(5)]), "desktop", 2)

    assert [b["text"] for b in measured.blocks] == ["t0", "t1"] and measured.truncated is True


async def test_exactly_the_cap_is_not_truncated():
    from iw_renderer.blocks import measure_blocks

    measured = await measure_blocks(FakeSession([{"text": "a"}, {"text": "b"}]), "desktop", 2)

    assert len(measured.blocks) == 2 and measured.truncated is False

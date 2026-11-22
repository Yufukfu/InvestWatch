import pytest

from iw_renderer.identity import browser_identity

DESKTOP = (
    ("sec-ch-ua", '"Chromium";v="146", "Not-A.Brand";v="24", "Google Chrome";v="146"'),
    ("sec-ch-ua-mobile", "?0"),
    ("sec-ch-ua-platform", '"Windows"'),
    ("user-agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36"),
    ("accept-language", "pl-PL,pl;q=0.9,en-US;q=0.8,en;q=0.7"),
)
MOBILE = (
    ("sec-ch-ua", '"Chromium";v="146", "Not-A.Brand";v="24", "Google Chrome";v="146"'),
    ("sec-ch-ua-mobile", "?1"),
    ("sec-ch-ua-platform", '"Android"'),
    ("user-agent", "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Mobile Safari/537.36"),
    ("accept-language", "pl-PL,pl;q=0.9,en-US;q=0.8,en;q=0.7"),
)


def test_a_chrome_major_that_differs_from_the_browser_is_rewritten_to_the_browsers():
    out = dict(browser_identity(DESKTOP, "147.0.7727.0"))

    assert "Chrome/147.0.0.0 Safari/537.36" in out["user-agent"]
    assert 'v="147"' in out["sec-ch-ua"] and 'v="146"' not in out["sec-ch-ua"]
    assert out["accept-language"] == "pl-PL,pl;q=0.9,en-US;q=0.8,en;q=0.7"
    assert out["sec-ch-ua-platform"] == '"Windows"'


def test_the_mobile_flavour_survives_the_rewrite():
    out = dict(browser_identity(MOBILE, "147.0.7727.0"))

    assert "Chrome/147.0.0.0 Mobile Safari/537.36" in out["user-agent"]
    assert out["sec-ch-ua-mobile"] == "?1"


def test_a_matching_major_is_left_unchanged():
    assert browser_identity(DESKTOP, "146.0.7000.1") == DESKTOP


def test_a_non_chrome_identity_is_refused():
    firefox = (("user-agent", "Mozilla/5.0 (X11; Linux x86_64; rv:147.0) Gecko/20100101 Firefox/147.0"),)
    with pytest.raises(ValueError, match="Chrome"):
        browser_identity(firefox, "147.0.7727.0")


def test_a_user_agent_without_a_chrome_version_is_refused():
    with pytest.raises(ValueError, match="Chrome"):
        browser_identity((("user-agent", "curl/8.4.0"),), "147.0.7727.0")

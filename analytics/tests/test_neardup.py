"""Near-duplicate detection and groups in Redis (analytics-embeddings task group 6). fakeredis only."""

from __future__ import annotations

import logging
import random
import time

import fakeredis
import pytest
import redis

from investwatch_analytics.config import NearDupSettings
from investwatch_analytics.neardup import NearDupIndex, build_index, shingles, signature
from investwatch_analytics.preprocessing import normalize

S = NearDupSettings()
#: First four values of signature({"zysk 20 procent co miesiac"}, 128) from a reference run (datasketch 2.0.0).
GOLDEN = [1098134003, 4137659716, 4183501174, 1815336871]
A, B, C, D = (f"{i}{i}{i}{i}{i}{i}{i}{i}-0000-4000-8000-000000000000" for i in range(1, 5))

_WORDS = ("zysk inwestycja rynek akcje kurs portfel ryzyko dywidenda fundusz bank kredyt lokata waluta "
          "notowania sesja spadek wzrost obligacje kapitał klient oferta konto zlecenie strategia plan cel "
          "miesiąc rok tydzień dzień procent wynik analiza raport sygnał trend wsparcie opór").split()


def text(n=300, seed=1) -> str:
    rnd = random.Random(seed)
    return " ".join(rnd.choice(_WORDS) + str(rnd.randint(0, 999)) for _ in range(n))


def edit(t: str, start: int, count: int, seed=99) -> str:
    words = t.split()
    rnd = random.Random(seed)
    for i in range(start, start + count):
        words[i] = "inne" + str(rnd.randint(0, 10**6))
    return " ".join(words)


@pytest.fixture
def r():
    return fakeredis.FakeRedis(decode_responses=True)


@pytest.fixture
def idx(r):
    return NearDupIndex(r, S)


class BrokenRedis:
    def __getattr__(self, name):
        def fail(*a, **k):
            raise redis.ConnectionError("down")
        return fail

    def pipeline(self, *a, **k):
        raise redis.ConnectionError("down")


# ---- shingles and signature -------------------------------------------------------------------


def test_shingles_are_word_5_grams_lowercase_without_diacritics():
    assert shingles(normalize("Zażółć Gęślą Jaźń raz dwa trzy"), 1000) == {
        "zazolc gesla jazn raz dwa", "gesla jazn raz dwa trzy"}


def test_fewer_than_five_words_have_no_shingle():
    assert shingles("raz dwa trzy cztery", 1000) == set()


def test_shingles_cut_at_max_chars():
    t = "a b c d e " * 10 + "x y z v w"
    assert "x y z v w" not in shingles(t, 50)


def test_signature_is_deterministic_and_sized():
    sig1 = signature(shingles(text(), 50_000), S.num_perm)
    sig2 = signature(shingles(text(), 50_000), S.num_perm)
    assert len(sig1) == S.num_perm and (sig1 == sig2).all()


def test_signature_matches_a_golden_value():
    """Stable across processes and machines (no per-process hash seed): other workers share the buckets."""
    sig = signature({"zysk 20 procent co miesiac"}, 128)
    assert [int(x) for x in sig[:4]] == GOLDEN


# ---- detection --------------------------------------------------------------------------------


def test_repost_with_changed_handle_joins_the_original(idx):
    original = "@alfa_inwest " + text() + " 🚀"
    repost = "@beta_zyski " + text() + " 💰"
    first = idx.observe(A, normalize(original), "https://x.com/alfa/1")
    second = idx.observe(B, normalize(repost), "https://x.com/beta/9")
    assert first.group_id == A and first.is_original and first.members == 1
    assert second.group_id == A and not second.is_original and second.members == 2
    assert second.original_url == "https://x.com/alfa/1" and second.similarity >= 0.8


def test_different_texts_are_not_grouped(idx):
    idx.observe(A, text(seed=1), "u1")
    res = idx.observe(B, text(seed=2), "u2")
    assert res.group_id == B and res.is_original and res.members == 1 and res.similarity is None


def test_changed_page_version_joins_the_group(idx):
    v1 = text(400)
    v2 = edit(v1, 200, 10)
    idx.observe(A, v1, "https://firma.example/oferta")
    res = idx.observe(B, v2, "https://firma.example/oferta")
    assert res.group_id == A and res.members == 2


def test_band_candidate_below_threshold_is_not_counted(r):
    strict = NearDupIndex(r, NearDupSettings(threshold=1.0))
    v1 = text(400)
    strict.observe(A, v1, "u1")
    res = strict.observe(B, edit(v1, 200, 10), "u2")
    assert res.group_id == B and res.members == 1


def test_redelivery_is_not_its_own_duplicate(idx):
    t = text()
    first = idx.observe(A, t, "u1")
    again = idx.observe(A, t, "u1")
    assert again.group_id == A and again.members == 1 and again.is_original
    assert first.group_id == again.group_id


def test_redelivery_of_a_member_keeps_its_group(idx):
    t = text()
    idx.observe(A, t, "u1")
    idx.observe(B, t, "u2")
    again = idx.observe(B, t, "u2")
    assert again.group_id == A and again.members == 2 and not again.is_original


def test_too_short_writes_nothing(idx, r):
    assert idx.observe(A, "raz dwa trzy cztery", "u") is None
    assert r.keys("*") == []


def est(a: str, b: str) -> float:
    return float((signature(shingles(a, 50_000), 128) == signature(shingles(b, 50_000), 128)).mean())


def test_best_group_wins(idx):
    base = text(400)
    far = edit(base, 50, 30, seed=1)      # J(base, far) ~0.84
    near = edit(base, 300, 15, seed=2)    # J(base, near) ~0.91; J(far, near) < 0.8
    assert est(far, near) < 0.8 <= est(base, far) < est(base, near)  # preconditions of this test
    assert idx.observe(A, far, "a").group_id == A
    assert idx.observe(B, near, "b").group_id == B
    res = idx.observe(C, base, "c")
    assert res.group_id == B and res.original_url == "b"


def test_keys_carry_the_ttl(r):
    idx = NearDupIndex(r, NearDupSettings(ttl_s=120))
    idx.observe(A, text(), "u1")
    idx.observe(B, text(), "u2")
    keys = r.keys("iw:neardup:v1:*")
    assert keys and all(0 < r.ttl(k) <= 120 for k in keys)
    assert r.get(f"iw:neardup:v1:doc:{B}") == A
    assert r.smembers(f"iw:neardup:v1:group:{A}") == {A, B}
    assert r.hget(f"iw:neardup:v1:meta:{B}", "url") == "u2"


def test_index_down_returns_none_and_logs(caplog):
    with caplog.at_level(logging.WARNING):
        assert NearDupIndex(BrokenRedis(), S).observe(A, text(), "u") is None
    assert any(getattr(x, "reason", None) == "neardup_unavailable" for x in caplog.records)


def test_log_has_no_text(idx, caplog):
    with caplog.at_level(logging.DEBUG):
        idx.observe(A, "Przepis na sernik " + text(), "u1")
        idx.observe(B, "Przepis na sernik " + text(), "u2")
    logs = "\n".join(f"{x.getMessage()} {x.__dict__}" for x in caplog.records)
    assert "sernik" not in logs and "neardup" in logs


def test_long_text_is_bounded_and_fast(idx):
    big = text(2_000) * 50          # about 2 MB
    assert len(shingles(big, S.max_chars)) <= S.max_chars // 2
    started = time.perf_counter()
    idx.observe(A, big, "u")
    assert time.perf_counter() - started < 1.0


def test_no_redis_no_index():
    assert build_index(S, None) is None
    assert isinstance(build_index(S, fakeredis.FakeRedis()), NearDupIndex)


def test_works_with_a_bytes_redis_client():
    raw = fakeredis.FakeRedis()
    idx = NearDupIndex(raw, S)
    idx.observe(A, text(), "https://a")
    res = idx.observe(B, text(), "https://b")
    assert res.group_id == A and res.original_url == "https://a"


# ---- mutation-check additions -----------------------------------------------------------------


def test_redelivery_reports_no_self_similarity(idx):
    t = text()
    idx.observe(A, t, "u1")
    assert idx.observe(A, t, "u1").similarity is None


def test_original_has_no_original_url(idx):
    first = idx.observe(A, text(), "https://a")
    idx.observe(B, text(), "https://b")
    assert first.original_url is None
    assert idx.observe(A, text(), "https://a").original_url is None


def test_similarity_exactly_at_threshold_counts(r):
    v1 = text(400)
    v2 = edit(v1, 200, 10)
    sim = float((signature(shingles(v1, 50_000), 128) == signature(shingles(v2, 50_000), 128)).mean())
    idx = NearDupIndex(r, NearDupSettings(threshold=sim))
    idx.observe(A, v1, "u1")
    assert idx.observe(B, v2, "u2").group_id == A


def test_copy_of_a_copy_joins_the_first_original(idx):
    base = text(400)
    b = edit(base, 50, 25, seed=3)     # J(base, b) ~0.86
    c = edit(b, 300, 25, seed=4)       # J(b, c) ~0.86, J(base, c) < 0.8
    assert est(base, c) < 0.8 <= min(est(base, b), est(b, c))  # preconditions
    idx.observe(A, base, "a")
    assert idx.observe(B, b, "b").group_id == A
    res = idx.observe(C, c, "c")
    assert res.group_id == A and res.original_url == "a" and res.members == 3


def test_redelivery_keeps_its_group_after_a_better_match_appears(idx):
    base = text(400)
    far = edit(base, 50, 30, seed=1)
    near = edit(base, 300, 15, seed=2)
    idx.observe(A, far, "a")
    idx.observe(B, near, "b")
    idx.observe(C, base, "c")           # joins B
    again = idx.observe(A, far, "a")
    assert again.group_id == A and again.similarity is None  # C's similarity belongs to group B


def test_corrupt_stored_signature_is_skipped(idx, r):
    idx.observe(A, text(), "u1")
    r.hset(f"iw:neardup:v1:meta:{A}", "sig", "AAAAAAA=")   # 5 bytes: not a signature
    res = idx.observe(B, text(), "u2")
    assert res is not None and res.group_id == B


# ---- review fixes (group 6) -------------------------------------------------------------------


def test_spam_flood_is_bounded(r, monkeypatch):
    import investwatch_analytics.neardup as nd

    monkeypatch.setattr(nd, "MAX_BUCKET_SIZE", 20)
    monkeypatch.setattr(nd, "BUCKET_SAMPLE", 8)
    idx = NearDupIndex(r, S)
    spam = text()
    ids = [f"{i:08d}-0000-4000-8000-000000000000" for i in range(60)]
    for d in ids:
        res = idx.observe(d, spam, "u")
    assert res.group_id == ids[0] and res.members == 60
    buckets = r.keys("iw:neardup:v1:b:*")
    assert buckets and max(r.scard(b) for b in buckets) == 20


def test_bucket_reads_are_sampled(r, monkeypatch):
    import investwatch_analytics.neardup as nd

    monkeypatch.setattr(nd, "BUCKET_SAMPLE", 8)
    idx = NearDupIndex(r, S)
    spam = text()
    for i in range(30):
        idx.observe(f"{i:08d}-0000-4000-8000-000000000000", spam, "u")
    seen = []
    real = r.pipeline

    def spy(*a, **k):
        pipe = real(*a, **k)
        orig = pipe.srandmember

        def srandmember(key, number=None):
            seen.append(number)
            return orig(key, number)

        pipe.srandmember = srandmember
        return pipe

    monkeypatch.setattr(r, "pipeline", spy)
    assert idx.observe(B, spam, "b").group_id.startswith("00000000")
    assert seen and set(seen) == {8}


def test_original_keys_refreshed_by_new_members(r):
    idx = NearDupIndex(r, NearDupSettings(ttl_s=1000))
    idx.observe(A, text(), "https://a")
    r.expire(f"iw:neardup:v1:meta:{A}", 5)
    r.expire(f"iw:neardup:v1:doc:{A}", 5)
    idx.observe(B, text(), "https://b")
    assert r.ttl(f"iw:neardup:v1:meta:{A}") > 5 and r.ttl(f"iw:neardup:v1:doc:{A}") > 5


def test_url_is_capped(idx, r):
    idx.observe(A, text(), "https://a/" + "x" * 10_000)
    assert len(r.hget(f"iw:neardup:v1:meta:{A}", "url")) == 2048


def test_bucket_key_matches_a_golden_value():
    """Little-endian bucket hashing: containers on any architecture share the buckets."""
    sig = signature({"zysk 20 procent co miesiac"}, 128)
    assert NearDupIndex(None, S)._bucket_keys(sig)[0] == "iw:neardup:v1:b:0:d747c2017afa4d1c"

from __future__ import annotations

import hashlib

import pytest

from investwatch_analytics.preprocessing import content_hash, guess_language, normalize, preprocess, split_sentences


def test_equivalent_texts_hash_the_same():
    composed = "Zarabiaj  na ETF\n\n ź"  # NBSP, runs of spaces/newlines, decomposed accent
    precomposed = "Zarabiaj na ETF ź"
    assert normalize(composed) == normalize(precomposed) == "Zarabiaj na ETF ź"
    assert content_hash(composed) == content_hash(precomposed)


def test_hash_is_sha256_of_normalized_text():
    assert content_hash(" a  b ") == hashlib.sha256(b"a b").hexdigest()


def test_different_texts_hash_differently():
    assert content_hash("zysk 8%") != content_hash("zysk 9%")


def test_sentence_split_keeps_legal_forms():
    text = "Reklama. Bank Przykładowy S.A. – Biuro Maklerskie. Otwórz IKE."
    assert [s.text for s in split_sentences(text)] == [
        "Reklama.",
        "Bank Przykładowy S.A. – Biuro Maklerskie.",
        "Otwórz IKE.",
    ]


def test_sentence_split_ignores_abbreviation_before_capital():
    text = "Kupuj np. ETF lub akcje. Biuro: ul. Marszałkowska 1. Zapraszamy."
    assert [s.text for s in split_sentences(text)] == [
        "Kupuj np. ETF lub akcje.",
        "Biuro: ul. Marszałkowska 1.",
        "Zapraszamy.",
    ]


def test_sentence_split_on_exclamation_question_and_footnote():
    text = "Zarabiaj 18%! Czy warto? *Ryzyko utraty kapitału."
    assert [s.text for s in split_sentences(text)] == ["Zarabiaj 18%!", "Czy warto?", "*Ryzyko utraty kapitału."]


@pytest.mark.parametrize(
    "text,expected",
    [
        ("Bonus 500 zł. Otwórz konto.", ["Bonus 500 zł.", "Otwórz konto."]),
        ("Zadzwoń: tel. 22 555 00 00. Biuro czynne.", ["Zadzwoń: tel. 22 555 00 00.", "Biuro czynne."]),
        ("Dr. Kowalski radzi. Prof. Nowak też.", ["Dr. Kowalski radzi.", "Prof. Nowak też."]),
        ("„Zarabiaj 18%!” Tak mówią klienci.", ["„Zarabiaj 18%!”", "Tak mówią klienci."]),
        ("Zarabiaj w bio! #forex #reklama", ["Zarabiaj w bio!", "#forex #reklama"]),
        ("Konto 0 zł\r\n\r\nNowość!", ["Konto 0 zł", "Nowość!"]),
        ("Kup np.\r\n\r\nAkcje.", ["Kup np.", "Akcje."]),
    ],
)
def test_sentence_split_review_cases(text, expected):
    assert [s.text for s in split_sentences(text)] == expected


def test_sentence_split_keeps_legal_form_before_capital():
    assert len(split_sentences("Alfa Inwestycje S.A. Dom Maklerski oferuje konta.")) == 1


def test_sentence_split_on_paragraph_break_without_punctuation():
    assert [s.text for s in split_sentences("Konto Premium\n\nZarabiaj 18%.")] == ["Konto Premium", "Zarabiaj 18%."]


def test_sentence_split_keeps_decimal_numbers():
    assert len(split_sentences("Zysk 7.5 procent rocznie. Koniec.")) == 2


def test_sentence_spans_point_into_original_text():
    text = "  Pierwsze  zdanie.\n\nDrugie zdanie!"
    for s in split_sentences(text):
        assert text[s.start:s.end] == s.text


@pytest.mark.parametrize(
    "text,lang",
    [
        ("Konto Premium Alfa Inwestycje. Zarabiaj nawet do 18% rocznie na portfelu ETF!", "pl"),
        ("Otwórz konto i inwestuj długoterminowo w fundusze.", "pl"),
        ("Świetna okazja: zarabiaj codziennie, the ultimate wybór.", "pl"),
        ("Risk warning: CFDs are complex instruments and come with a high risk of losing money.", "en"),
    ],
)
def test_language_guess(text, lang):
    assert guess_language(text) == lang


def test_language_guess_empty_is_none():
    assert guess_language("   ") is None


def test_preprocess_bundle():
    p = preprocess("Reklama.  Inwestuj z nami.")
    assert p.normalized == "Reklama. Inwestuj z nami."
    assert p.lang == "pl"
    assert len(p.sentences) == 2
    assert p.content_hash == content_hash("Reklama. Inwestuj z nami.")


def test_preprocess_empty_text():
    p = preprocess(" \n\t ")
    assert p.is_empty
    assert p.sentences == []


@pytest.mark.parametrize(
    "text, expected",
    [
        ("Wszystko jest ok. Zysk 15% rocznie.", ["Wszystko jest ok.", "Zysk 15% rocznie."]),
        ("Zysk wynosi ok. 15% rocznie.", ["Zysk wynosi ok. 15% rocznie."]),
        ("Zadzwoń, tel. 22 123 45 67.", ["Zadzwoń, tel. 22 123 45 67."]),
        ("Zgodnie z art. 44 ust. 2 rozporządzenia.", ["Zgodnie z art. 44 ust. 2 rozporządzenia."]),
        ("Zaufaj im. Zarabiaj 8%.", ["Zaufaj im.", "Zarabiaj 8%."]),
        ("Zarobiliśmy 5 tys. Zainwestuj teraz.", ["Zarobiliśmy 5 tys.", "Zainwestuj teraz."]),
        ("W 2024 r. Alfa Inwestycje zarobiła 12%.", ["W 2024 r. Alfa Inwestycje zarobiła 12%."]),
        ("Od 2020r. Nasi klienci zarabiają.", ["Od 2020r. Nasi klienci zarabiają."]),
        ("Kup np. Bitcoin. Zarabiaj.", ["Kup np. Bitcoin.", "Zarabiaj."]),
        ("Pisze prof. Nowak. Zarabiaj.", ["Pisze prof. Nowak.", "Zarabiaj."]),
    ],
)
def test_abbreviations_that_are_also_words(text, expected):
    assert [s.text for s in split_sentences(text)] == expected

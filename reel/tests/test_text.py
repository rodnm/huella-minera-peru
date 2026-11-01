"""SRT formatting, karaoke grouping and number normalization before WER."""
from reelkit.text import Word, group_words, merge_fragments, normalize_for_wer, srt_timestamp, to_srt


# --- SRT timestamps -----------------------------------------------------------

def test_srt_timestamp_formats_hours_minutes_seconds_millis():
    assert srt_timestamp(0) == "00:00:00,000"
    assert srt_timestamp(3661.5) == "01:01:01,500"


def test_srt_timestamp_rounds_instead_of_truncating_float_error():
    # 2.3 % 1 * 1000 == 299.99999999999983: truncation would give ",299"
    assert srt_timestamp(2.3) == "00:00:02,300"
    assert srt_timestamp(59.9996) == "00:01:00,000"


def test_srt_timestamp_clamps_negative_times_to_zero():
    assert srt_timestamp(-0.04) == "00:00:00,000"


def test_to_srt_numbers_blocks_and_keeps_them_in_order_without_overlap():
    blocks = [
        [Word(0.30, 0.62, "Visto"), Word(0.62, 0.90, "desde"), Word(0.90, 1.40, "el")],
        [Word(1.35, 1.80, "espacio.")],
    ]
    srt = to_srt(blocks)
    assert srt.splitlines()[:4] == ["1", "00:00:00,300 --> 00:00:01,350", "Visto desde el", ""]
    assert srt.splitlines()[4:7] == ["2", "00:00:01,350 --> 00:00:01,800", "espacio."]
    assert srt.endswith("\n")


# --- karaoke blocks ---------------------------------------------------------

def _words(text, step=0.3):
    return [Word(i * step, i * step + step, w) for i, w in enumerate(text.split())]


def test_group_words_never_exceeds_four_words_and_keeps_every_word_in_order():
    words = _words("el perú minero se encendió en solo doce años y nadie lo vio venir desde abajo")
    blocks = group_words(words)
    assert all(1 <= len(b) <= 4 for b in blocks)
    assert [w for b in blocks for w in b] == words


def test_group_words_closes_a_block_at_punctuation():
    words = _words("Visto desde el espacio, el Perú minero se encendió.")
    blocks = group_words(words)
    assert [" ".join(w.text for w in b) for b in blocks] == [
        "Visto desde el espacio,", "el Perú minero se", "encendió."]


def test_group_words_closes_a_block_at_a_long_silence():
    words = [Word(0.0, 0.3, "uno"), Word(0.3, 0.6, "dos"), Word(1.6, 1.9, "tres")]
    assert [len(b) for b in group_words(words)] == [2, 1]


def test_merge_fragments_glues_decimal_and_percent_pieces_to_the_previous_word():
    words = [Word(0, 0.4, "8"), Word(0.4, 0.6, ".7"), Word(0.6, 1.0, "126"), Word(1.0, 1.2, "%")]
    assert merge_fragments(words) == [Word(0, 0.6, "8.7"), Word(0.6, 1.2, "126%")]


# --- normalization before WER ------------------------------------------------

def test_normalize_for_wer_turns_digits_and_percent_into_spanish_words():
    assert normalize_for_wer("126%") == normalize_for_wer("ciento veintiséis por ciento")
    assert normalize_for_wer("126%") == "ciento veintiseis por ciento"


def test_normalize_for_wer_reads_thousands_separators_as_one_number():
    assert normalize_for_wer("12,984 focos") == "doce mil novecientos ochenta y cuatro focos"
    assert normalize_for_wer("12.984") == normalize_for_wer("12,984")


def test_normalize_for_wer_reads_decimals_with_punto():
    assert normalize_for_wer("8.7 km") == "ocho punto siete km"
    assert normalize_for_wer("8,7") == "ocho punto siete"


def test_normalize_for_wer_handles_years_case_accents_and_punctuation():
    assert normalize_for_wer("De 2013 a 2024, ¿Perú?") == "de dos mil trece a dos mil veinticuatro peru"

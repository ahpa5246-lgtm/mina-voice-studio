from studio.text import split_speech, normalize_text, MAX_SEGMENT_CHARS


def test_short_arabic_stays_in_one_segment():
    sample = "السَّلَامُ عليكم، شلونكم اليوم؟"
    assert split_speech(sample) == [sample]


def test_arabic_long_document_keeps_words_and_lengths():
    text = " ".join(["هذه تجربة لقياس سلامة تقسيم الجمل العربية."] * 80)
    chunks = split_speech(text)
    assert len(chunks) > 2
    assert max(map(len, chunks)) <= MAX_SEGMENT_CHARS
    assert " ".join(chunks) == text


def test_huge_unbroken_input_is_bounded():
    chunks = split_speech("ا" * 1203)
    assert "".join(chunks) == "ا" * 1203
    assert max(map(len, chunks)) <= MAX_SEGMENT_CHARS


def test_no_control_characters_are_passed_to_model():
    assert normalize_text("مرحبا\x00\x07\nبك") == "مرحبا  \nبك"


def test_empty_text_yields_no_work():
    assert split_speech("   \t  ") == []


def test_sentence_breaks_prioritized_when_bounded():
    text = "نعم. انتهينا من التجربة؟ والآن نبدأ."
    assert split_speech(text, max_chars=25) == ["نعم.", "انتهينا من التجربة؟", "والآن نبدأ."]


def test_invalid_chunk_size():
    import pytest
    with pytest.raises(ValueError):
        split_speech("hello", max_chars=4)

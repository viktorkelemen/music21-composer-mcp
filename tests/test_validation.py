"""Tests for input validation and format detection."""

import pytest
from music21 import stream, note

from composer_mcp.core.models import InputFormat
from composer_mcp.core.validation import (
    detect_format,
    parse_input,
    parse_note_list,
    stream_to_musicxml,
)
from composer_mcp.errors import EmptyInputError, ParseError


class TestDetectFormat:
    """Tests for format detection."""

    def test_detect_musicxml_with_declaration(self):
        """MusicXML with XML declaration."""
        xml = '<?xml version="1.0"?><score-partwise></score-partwise>'
        assert detect_format(xml) == InputFormat.MUSICXML

    def test_detect_musicxml_with_score_tag(self):
        """MusicXML starting with score tag."""
        xml = "<score-partwise><part></part></score-partwise>"
        assert detect_format(xml) == InputFormat.MUSICXML

    def test_detect_abc(self):
        """ABC notation."""
        abc = "X:1\nT:Test\nM:4/4\nK:C\nCDEF|"
        assert detect_format(abc) == InputFormat.ABC

    def test_detect_abc_key_only(self):
        """ABC with just key field."""
        abc = "K:C\nCDEF"
        assert detect_format(abc) == InputFormat.ABC

    def test_detect_notes_simple(self):
        """Simple note list."""
        notes = "C4, D4, E4, G4"
        assert detect_format(notes) == InputFormat.NOTES

    def test_detect_notes_with_durations(self):
        """Note list with durations."""
        notes = "C4:q D4:q E4:h"
        assert detect_format(notes) == InputFormat.NOTES

    def test_detect_notes_lowercase(self):
        """Note list with lowercase."""
        notes = "c4 d4 e4"
        assert detect_format(notes) == InputFormat.NOTES

    def test_empty_input_raises(self):
        """Empty input raises EmptyInputError."""
        with pytest.raises(EmptyInputError):
            detect_format("")

    def test_whitespace_only_raises(self):
        """Whitespace-only input raises EmptyInputError."""
        with pytest.raises(EmptyInputError):
            detect_format("   \n\t  ")

    def test_unknown_format_raises(self):
        """Unknown format raises ParseError."""
        with pytest.raises(ParseError):
            detect_format("this is not music")


class TestParseNoteList:
    """Tests for note list parsing."""

    def test_simple_notes(self):
        """Parse simple note list."""
        s = parse_note_list("C4, D4, E4")
        notes = list(s.notes)
        assert len(notes) == 3
        assert notes[0].nameWithOctave == "C4"
        assert notes[1].nameWithOctave == "D4"
        assert notes[2].nameWithOctave == "E4"

    def test_notes_with_durations(self):
        """Parse notes with durations."""
        s = parse_note_list("C4:h, D4:q, E4:e")
        notes = list(s.notes)
        assert len(notes) == 3
        assert notes[0].duration.quarterLength == 2.0  # half
        assert notes[1].duration.quarterLength == 1.0  # quarter
        assert notes[2].duration.quarterLength == 0.5  # eighth

    def test_dotted_notes(self):
        """Parse dotted notes."""
        s = parse_note_list("C4:qd")  # dotted quarter
        notes = list(s.notes)
        assert notes[0].duration.quarterLength == 1.5

    def test_space_separated(self):
        """Parse space-separated notes."""
        s = parse_note_list("C4 D4 E4")
        notes = list(s.notes)
        assert len(notes) == 3

    def test_sharps_and_flats(self):
        """Parse accidentals."""
        s = parse_note_list("C#4, Bb4, F#5")
        notes = list(s.notes)
        assert notes[0].pitch.accidental.name == "sharp"
        assert notes[1].pitch.accidental.name == "flat"

    def test_default_duration_quarter(self):
        """Notes without duration default to quarter."""
        s = parse_note_list("C4, D4")
        notes = list(s.notes)
        assert all(n.duration.quarterLength == 1.0 for n in notes)


class TestParseInput:
    """Tests for parse_input with different formats."""

    def test_parse_notes_auto(self):
        """Auto-detect and parse notes."""
        s = parse_input("C4, D4, E4")
        assert len(list(s.notes)) == 3

    def test_parse_notes_explicit(self):
        """Explicit format for notes."""
        s = parse_input("C4 D4 E4", InputFormat.NOTES)
        assert len(list(s.notes)) == 3

    def test_empty_string_raises(self):
        """Empty string raises EmptyInputError."""
        with pytest.raises(EmptyInputError):
            parse_input("")


class TestStreamToMusicxml:
    """Tests for MusicXML export."""

    def test_basic_export(self):
        """Export simple stream to MusicXML."""
        s = stream.Stream()
        s.append(note.Note("C4"))
        s.append(note.Note("D4"))

        xml = stream_to_musicxml(s)
        assert "<?xml" in xml or "<score" in xml
        assert len(xml) > 100  # Should be substantial XML

"""Tests for harmony/chord voicing."""

import pytest

from composer_mcp.core.harmony import (
    apply_range_constraints,
    close_voicing,
    drop2_voicing,
    drop3_voicing,
    get_intervals_from_bass,
    open_voicing,
    parse_chord_symbol,
    quartal_voicing,
    realize_chord,
)
from composer_mcp.core.models import RealizeChordRequest, VoicingStyle
from composer_mcp.errors import InvalidChordSymbolError


class TestParseChordSymbol:
    """Tests for chord symbol parsing."""

    def test_parse_major_triad(self):
        """Parse C major triad."""
        cs = parse_chord_symbol("C")
        assert len(cs.pitches) == 3

    def test_parse_major_seventh(self):
        """Parse Cmaj7."""
        cs = parse_chord_symbol("Cmaj7")
        assert len(cs.pitches) == 4

    def test_parse_minor_seventh(self):
        """Parse Dm7."""
        cs = parse_chord_symbol("Dm7")
        assert len(cs.pitches) == 4
        # Root should be D
        assert cs.root().name == "D"

    def test_parse_dominant_seventh(self):
        """Parse G7."""
        cs = parse_chord_symbol("G7")
        assert len(cs.pitches) == 4

    def test_parse_diminished(self):
        """Parse Bdim."""
        cs = parse_chord_symbol("Bdim")
        assert cs.root().name == "B"

    def test_invalid_symbol_raises(self):
        """Invalid chord symbol raises error."""
        with pytest.raises(InvalidChordSymbolError):
            parse_chord_symbol("XYZ123")


class TestCloseVoicing:
    """Tests for close position voicing."""

    def test_close_voicing_within_octave(self):
        """Close voicing spans roughly an octave."""
        from music21 import pitch
        pitches = [pitch.Pitch("C4"), pitch.Pitch("E4"), pitch.Pitch("G4"), pitch.Pitch("B4")]
        voiced = close_voicing(pitches)
        span = voiced[-1].midi - voiced[0].midi
        # Close voicing should be within ~12 semitones (octave + a bit)
        assert span <= 14

    def test_inversion_changes_bass(self):
        """First inversion has third in bass."""
        from music21 import pitch
        pitches = [pitch.Pitch("C4"), pitch.Pitch("E4"), pitch.Pitch("G4")]
        root_pos = close_voicing(pitches, inversion=0)
        first_inv = close_voicing(pitches, inversion=1)
        # First inversion should have E as lowest
        assert first_inv[0].name == "E"

    def test_second_inversion(self):
        """Second inversion has fifth in bass."""
        from music21 import pitch
        pitches = [pitch.Pitch("C4"), pitch.Pitch("E4"), pitch.Pitch("G4")]
        second_inv = close_voicing(pitches, inversion=2)
        assert second_inv[0].name == "G"


class TestOpenVoicing:
    """Tests for open position voicing."""

    def test_open_voicing_wider_than_close(self):
        """Open voicing has larger span than close."""
        from music21 import pitch
        pitches = [pitch.Pitch("C4"), pitch.Pitch("E4"), pitch.Pitch("G4"), pitch.Pitch("B4")]
        close = close_voicing(pitches)
        opened = open_voicing(pitches)
        close_span = close[-1].midi - close[0].midi
        open_span = opened[-1].midi - opened[0].midi
        assert open_span > close_span


class TestDrop2Voicing:
    """Tests for drop 2 voicing."""

    def test_drop2_moves_second_from_top(self):
        """Drop 2 moves second-from-top note down an octave."""
        from music21 import pitch
        pitches = [pitch.Pitch("C4"), pitch.Pitch("E4"), pitch.Pitch("G4"), pitch.Pitch("B4")]
        dropped = drop2_voicing(pitches)
        # Result should have wider spacing due to dropped note
        assert len(dropped) == 4
        # G should be in a lower octave
        g_notes = [p for p in dropped if p.name == "G"]
        assert len(g_notes) == 1


class TestDrop3Voicing:
    """Tests for drop 3 voicing."""

    def test_drop3_four_note_chord(self):
        """Drop 3 works on four-note chord."""
        from music21 import pitch
        pitches = [pitch.Pitch("C4"), pitch.Pitch("E4"), pitch.Pitch("G4"), pitch.Pitch("B4")]
        dropped = drop3_voicing(pitches)
        assert len(dropped) == 4


class TestQuartalVoicing:
    """Tests for quartal (fourths-based) voicing."""

    def test_quartal_stacks_fourths(self):
        """Quartal voicing stacks perfect fourths."""
        from music21 import pitch
        root = pitch.Pitch("C4")
        voicing = quartal_voicing(root)
        assert len(voicing) == 4
        # Each interval should be 5 semitones (P4)
        for i in range(len(voicing) - 1):
            interval = voicing[i + 1].midi - voicing[i].midi
            assert interval == 5


class TestApplyRangeConstraints:
    """Tests for range constraint application."""

    def test_pitches_stay_in_range(self):
        """Pitches are adjusted to fit range."""
        from music21 import pitch
        pitches = [pitch.Pitch("C2"), pitch.Pitch("G2"), pitch.Pitch("C3")]
        constrained = apply_range_constraints(pitches, "E2", "G4", "piano")
        for p in constrained:
            assert pitch.Pitch("E2").midi <= p.midi <= pitch.Pitch("G4").midi

    def test_guitar_max_six_notes(self):
        """Guitar voicing limited to 6 notes."""
        from music21 import pitch
        pitches = [
            pitch.Pitch("C3"), pitch.Pitch("E3"), pitch.Pitch("G3"),
            pitch.Pitch("B3"), pitch.Pitch("D4"), pitch.Pitch("F4"),
            pitch.Pitch("A4"), pitch.Pitch("C5"),
        ]
        constrained = apply_range_constraints(pitches, None, None, "guitar")
        assert len(constrained) <= 6


class TestGetIntervalsFromBass:
    """Tests for interval calculation."""

    def test_major_triad_intervals(self):
        """Major triad has M3 and P5 from bass."""
        from music21 import pitch
        pitches = [pitch.Pitch("C4"), pitch.Pitch("E4"), pitch.Pitch("G4")]
        intervals = get_intervals_from_bass(pitches)
        assert "M3" in intervals
        assert "P5" in intervals


class TestRealizeChord:
    """Tests for full chord realization."""

    def test_basic_realization(self):
        """Realize a basic chord."""
        request = RealizeChordRequest(chord_symbol="Cmaj7")
        response = realize_chord(request)
        assert response.success is True
        assert "voicing" in response.data
        assert len(response.data["voicing"]["notes"]) >= 4

    def test_voicing_style_applied(self):
        """Voicing style is reflected in analysis."""
        request = RealizeChordRequest(
            chord_symbol="Dm7",
            voicing_style=VoicingStyle.DROP2,
        )
        response = realize_chord(request)
        assert response.data["analysis"]["voicing_style"] == "drop2"

    def test_inversion_in_analysis(self):
        """Inversion is tracked in analysis."""
        request = RealizeChordRequest(
            chord_symbol="C",
            inversion=1,
        )
        response = realize_chord(request)
        assert response.data["analysis"]["inversion"] == 1

    def test_slash_chord_bass(self):
        """Slash chord puts specified note in bass."""
        request = RealizeChordRequest(
            chord_symbol="G",
            bass_note="D3",
        )
        response = realize_chord(request)
        # First note should be D
        assert response.data["voicing"]["notes"][0].startswith("D")

    def test_instrument_range_respected(self):
        """SATB range is respected."""
        from music21 import pitch
        request = RealizeChordRequest(
            chord_symbol="Cmaj7",
            instrument="satb",
        )
        response = realize_chord(request)
        for note_str in response.data["voicing"]["notes"]:
            note_midi = pitch.Pitch(note_str).midi
            # SATB range is E2 to A5
            assert pitch.Pitch("E2").midi <= note_midi <= pitch.Pitch("A5").midi

    def test_alternatives_provided(self):
        """Response includes alternative voicings."""
        request = RealizeChordRequest(chord_symbol="Am7")
        response = realize_chord(request)
        assert "alternatives" in response.data
        assert len(response.data["alternatives"]) >= 1

    def test_musicxml_included(self):
        """MusicXML is included in voicing."""
        request = RealizeChordRequest(chord_symbol="F")
        response = realize_chord(request)
        assert response.data["voicing"]["musicxml"] is not None
        assert "<?xml" in response.data["voicing"]["musicxml"]

    def test_midi_pitches_included(self):
        """MIDI pitch numbers are included."""
        request = RealizeChordRequest(chord_symbol="C")
        response = realize_chord(request)
        midi_pitches = response.data["voicing"]["midi_pitches"]
        assert len(midi_pitches) > 0
        assert all(isinstance(p, int) for p in midi_pitches)

    def test_quartal_voicing(self):
        """Quartal voicing creates fourths-based structure."""
        request = RealizeChordRequest(
            chord_symbol="C",
            voicing_style=VoicingStyle.QUARTAL,
        )
        response = realize_chord(request)
        assert response.success is True
        midi_pitches = response.data["voicing"]["midi_pitches"]
        # Quartal voicing stacks P4s (5 semitones each)
        for i in range(len(midi_pitches) - 1):
            interval = midi_pitches[i + 1] - midi_pitches[i]
            assert interval == 5

    def test_custom_range(self):
        """Custom range is respected."""
        from music21 import pitch
        request = RealizeChordRequest(
            chord_symbol="Cmaj7",
            range_low="C3",
            range_high="C4",
        )
        response = realize_chord(request)
        for note_str in response.data["voicing"]["notes"]:
            note_midi = pitch.Pitch(note_str).midi
            assert pitch.Pitch("C3").midi <= note_midi <= pitch.Pitch("C4").midi

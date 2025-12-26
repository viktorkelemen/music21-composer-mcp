"""Tests for melody generation."""

import pytest

from composer_mcp.core.melody import (
    generate_melody,
    generate_rhythm_pattern,
    get_contour_bias,
    get_scale_pitches_in_range,
    parse_key_signature,
    select_next_pitch,
)
from composer_mcp.core.models import ContourType, MelodyRequest, RhythmicDensity
from composer_mcp.errors import InvalidRangeError, UnsatisfiableConstraintsError


class TestParseKeySignature:
    """Tests for key signature parsing."""

    def test_parse_major_key(self):
        """Parse C major."""
        k = parse_key_signature("C major")
        assert k.tonic.name == "C"
        assert k.mode == "major"

    def test_parse_minor_key(self):
        """Parse A minor."""
        k = parse_key_signature("A minor")
        assert k.tonic.name == "A"
        assert k.mode == "minor"

    def test_parse_modal_key(self):
        """Parse D dorian."""
        k = parse_key_signature("D dorian")
        assert k.tonic.name == "D"
        assert k.mode == "dorian"

    def test_parse_sharps(self):
        """Parse F# minor."""
        k = parse_key_signature("F# minor")
        assert "F#" in k.tonic.name or k.tonic.name == "F#"

    def test_invalid_format_raises(self):
        """Invalid format raises ValueError."""
        with pytest.raises(ValueError, match="Invalid key format"):
            parse_key_signature("invalid")


class TestGetScalePitchesInRange:
    """Tests for scale pitch extraction."""

    def test_c_major_one_octave(self):
        """C major from C4 to C5 gives 8 notes."""
        from music21 import key
        k = key.Key("C", "major")
        pitches = get_scale_pitches_in_range(k, "C4", "C5")
        assert len(pitches) == 8
        assert pitches[0].nameWithOctave == "C4"
        assert pitches[-1].nameWithOctave == "C5"

    def test_range_too_narrow(self):
        """Range where low >= high raises error."""
        from music21 import key
        k = key.Key("C", "major")
        with pytest.raises(InvalidRangeError):
            get_scale_pitches_in_range(k, "C5", "C4")

    def test_pitches_are_sorted(self):
        """Returned pitches are in ascending order."""
        from music21 import key
        k = key.Key("G", "major")
        pitches = get_scale_pitches_in_range(k, "G3", "G5")
        for i in range(len(pitches) - 1):
            assert pitches[i].midi < pitches[i + 1].midi


class TestGenerateRhythmPattern:
    """Tests for rhythm pattern generation."""

    def test_sparse_rhythm_length(self):
        """Sparse rhythm fills correct duration."""
        import random
        rng = random.Random(42)
        rhythm = generate_rhythm_pattern(RhythmicDensity.SPARSE, "4/4", 2, rng)
        # 2 measures of 4/4 = 8 quarter notes
        assert abs(sum(rhythm) - 8.0) < 0.01

    def test_dense_has_more_notes(self):
        """Dense rhythm has more notes than sparse."""
        import random
        rng = random.Random(42)
        sparse = generate_rhythm_pattern(RhythmicDensity.SPARSE, "4/4", 4, rng)
        rng = random.Random(42)
        dense = generate_rhythm_pattern(RhythmicDensity.DENSE, "4/4", 4, rng)
        assert len(dense) > len(sparse)

    def test_different_time_signature(self):
        """3/4 time signature produces correct length."""
        import random
        rng = random.Random(42)
        rhythm = generate_rhythm_pattern(RhythmicDensity.MEDIUM, "3/4", 4, rng)
        # 4 measures of 3/4 = 12 quarter notes
        assert abs(sum(rhythm) - 12.0) < 0.01


class TestGetContourBias:
    """Tests for contour bias calculation."""

    def test_arch_early_is_up(self):
        """Arch contour early in phrase has upward bias."""
        bias = get_contour_bias(0.2, ContourType.ARCH)
        assert bias > 0

    def test_arch_late_is_down(self):
        """Arch contour late in phrase has downward bias."""
        bias = get_contour_bias(0.8, ContourType.ARCH)
        assert bias < 0

    def test_ascending_always_up(self):
        """Ascending contour always biases up."""
        for pos in [0.0, 0.5, 1.0]:
            assert get_contour_bias(pos, ContourType.ASCENDING) > 0

    def test_descending_always_down(self):
        """Descending contour always biases down."""
        for pos in [0.0, 0.5, 1.0]:
            assert get_contour_bias(pos, ContourType.DESCENDING) < 0

    def test_static_is_neutral(self):
        """Static contour has no bias."""
        assert get_contour_bias(0.5, ContourType.STATIC) == 0

    def test_none_is_neutral(self):
        """No contour has no bias."""
        assert get_contour_bias(0.5, None) == 0


class TestGenerateMelody:
    """Tests for full melody generation."""

    def test_basic_generation(self):
        """Generate a basic melody."""
        request = MelodyRequest(
            key="C major",
            length_measures=2,
            time_signature="4/4",
            seed=42,
        )
        response = generate_melody(request)
        assert response.success is True
        assert "melody" in response.data
        assert response.data["metadata"]["measures"] == 2

    def test_seed_reproducibility(self):
        """Same seed produces same melody."""
        request = MelodyRequest(
            key="C major",
            length_measures=4,
            seed=123,
        )
        r1 = generate_melody(request)
        r2 = generate_melody(request)
        assert r1.data["melody"]["notes"] == r2.data["melody"]["notes"]

    def test_range_constraint_respected(self):
        """Generated notes stay within range."""
        request = MelodyRequest(
            key="C major",
            length_measures=4,
            range_low="E4",
            range_high="G5",
            seed=42,
        )
        response = generate_melody(request)
        from music21 import pitch
        low_midi = pitch.Pitch("E4").midi
        high_midi = pitch.Pitch("G5").midi
        for note in response.data["melody"]["notes"]:
            note_midi = pitch.Pitch(note["pitch"]).midi
            assert low_midi <= note_midi <= high_midi

    def test_start_note_constraint(self):
        """Start note is respected when in scale."""
        request = MelodyRequest(
            key="C major",
            length_measures=2,
            start_note="E4",
            seed=42,
        )
        response = generate_melody(request)
        first_note = response.data["melody"]["notes"][0]["pitch"]
        assert first_note == "E4"

    def test_end_note_constraint(self):
        """End note is respected when in scale."""
        request = MelodyRequest(
            key="C major",
            length_measures=2,
            end_note="G4",
            seed=42,
        )
        response = generate_melody(request)
        last_note = response.data["melody"]["notes"][-1]["pitch"]
        assert last_note == "G4"

    def test_narrow_range_fails(self):
        """Too narrow range raises error."""
        request = MelodyRequest(
            key="C major",
            length_measures=2,
            range_low="C4",
            range_high="D4",  # Only 2 scale tones
        )
        with pytest.raises(UnsatisfiableConstraintsError):
            generate_melody(request)

    def test_contour_influences_shape(self):
        """Arch contour produces expected melodic shape."""
        request = MelodyRequest(
            key="C major",
            length_measures=4,
            contour=ContourType.ARCH,
            range_low="C4",
            range_high="C6",
            seed=42,
        )
        response = generate_melody(request)
        notes = response.data["melody"]["notes"]

        # Find highest note - should be in middle third
        from music21 import pitch
        midi_values = [pitch.Pitch(n["pitch"]).midi for n in notes]
        max_idx = midi_values.index(max(midi_values))
        relative_pos = max_idx / len(notes)
        # Arch peak should be roughly in middle (0.3-0.7)
        assert 0.2 <= relative_pos <= 0.8

    def test_warning_for_adjusted_start_note(self):
        """Non-scale start note produces warning."""
        request = MelodyRequest(
            key="C major",
            length_measures=2,
            start_note="C#4",  # Not in C major
            seed=42,
        )
        response = generate_melody(request)
        assert response.success is True
        assert len(response.warnings) > 0
        assert any(w.code == "START_NOTE_ADJUSTED" for w in response.warnings)

    def test_metadata_includes_seed(self):
        """Response includes seed used."""
        request = MelodyRequest(
            key="G major",
            length_measures=2,
        )
        response = generate_melody(request)
        assert response.data["metadata"]["seed_used"] is not None

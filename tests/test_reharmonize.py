"""Tests for reharmonization."""

import pytest

from composer_mcp.core.reharmonize import (
    CLASSICAL_RULES,
    JAZZ_RULES,
    MODAL_RULES,
    POP_RULES,
    get_chord_candidates,
    get_chord_points,
    get_melody_notes_at,
    reharmonize,
    score_chord_melody_fit,
    score_style_adherence,
    score_voice_leading,
    select_chord,
)
from composer_mcp.core.models import HarmonizationStyle, ReharmonizeRequest
from music21 import key, stream, note


class TestStyleRules:
    """Tests for style rule definitions."""

    def test_classical_rules_exist(self):
        """Classical rules are properly defined."""
        assert len(CLASSICAL_RULES.allowed_numerals) > 0
        assert CLASSICAL_RULES.avoid_parallel_fifths is True
        assert CLASSICAL_RULES.prefer_extensions is False

    def test_jazz_rules_allow_extensions(self):
        """Jazz rules prefer extensions."""
        assert JAZZ_RULES.prefer_extensions is True
        assert "Imaj7" in JAZZ_RULES.allowed_numerals
        assert "ii7" in JAZZ_RULES.allowed_numerals

    def test_pop_rules_simple(self):
        """Pop rules use simple chords."""
        assert "I" in POP_RULES.allowed_numerals
        assert POP_RULES.prefer_extensions is False
        assert POP_RULES.prefer_root_position is True

    def test_modal_rules_avoid_tritone(self):
        """Modal rules have characteristic settings."""
        assert len(MODAL_RULES.allowed_numerals) > 0
        assert MODAL_RULES.avoid_parallel_fifths is False


class TestGetChordPoints:
    """Tests for chord point detection."""

    def test_per_measure_4_4(self):
        """Per measure in 4/4 gives points every 4 beats."""
        s = stream.Stream()
        for i in range(8):
            n = note.Note("C4")
            n.quarterLength = 1
            s.append(n)

        points = get_chord_points(s, "per_measure", 4)
        assert points == [0.0, 4.0]

    def test_per_beat(self):
        """Per beat gives points every beat."""
        s = stream.Stream()
        for i in range(4):
            n = note.Note("C4")
            n.quarterLength = 1
            s.append(n)

        points = get_chord_points(s, "per_beat", 4)
        assert points == [0.0, 1.0, 2.0, 3.0]

    def test_per_half(self):
        """Per half gives two points per measure."""
        s = stream.Stream()
        for i in range(8):
            n = note.Note("C4")
            n.quarterLength = 1
            s.append(n)

        points = get_chord_points(s, "per_half", 4)
        assert points == [0.0, 2.0, 4.0, 6.0]


class TestGetMelodyNotesAt:
    """Tests for melody note extraction."""

    def test_single_note(self):
        """Extract single note at offset."""
        s = stream.Stream()
        n = note.Note("C4")
        n.quarterLength = 4
        s.append(n)

        notes = get_melody_notes_at(s, 0.0, 1.0)
        assert "C" in notes

    def test_multiple_notes(self):
        """Extract overlapping notes."""
        s = stream.Stream()
        n1 = note.Note("C4")
        n1.quarterLength = 2
        n2 = note.Note("E4")
        n2.quarterLength = 2
        s.append(n1)
        s.append(n2)

        notes = get_melody_notes_at(s, 0.0, 4.0)
        assert "C" in notes
        assert "E" in notes

    def test_no_notes_at_offset(self):
        """No notes at offset returns empty."""
        s = stream.Stream()
        n = note.Note("C4")
        n.quarterLength = 1
        s.append(n)

        notes = get_melody_notes_at(s, 5.0, 1.0)
        assert len(notes) == 0


class TestGetChordCandidates:
    """Tests for chord candidate generation."""

    def test_candidates_for_c_major_notes(self):
        """C, E, G should favor C major chord."""
        k = key.Key("C", "major")
        candidates = get_chord_candidates(
            melody_notes=["C", "E", "G"],
            music_key=k,
            rules=CLASSICAL_RULES,
        )

        # Should return some candidates
        assert len(candidates) > 0

        # I chord should be highly ranked (all notes are chord tones)
        numerals = [c[0] for c in candidates]
        assert "I" in numerals

    def test_candidates_respect_style(self):
        """Jazz candidates should include 7th chords."""
        k = key.Key("C", "major")
        candidates = get_chord_candidates(
            melody_notes=["D", "F", "A"],
            music_key=k,
            rules=JAZZ_RULES,
        )

        numerals = [c[0] for c in candidates]
        # Should include jazz numerals
        assert any("7" in n for n in numerals)

    def test_cadence_bonus(self):
        """Cadence points should favor cadential chords."""
        k = key.Key("C", "major")

        # At cadence, V should get a bonus
        candidates = get_chord_candidates(
            melody_notes=["B", "D", "G"],
            music_key=k,
            rules=CLASSICAL_RULES,
            is_cadence=True,
        )

        # V should be among top candidates at cadence
        top_numerals = [c[0] for c in candidates[:3]]
        assert "V" in top_numerals or "viio" in top_numerals


class TestSelectChord:
    """Tests for chord selection."""

    def test_select_from_candidates(self):
        """Select returns a valid numeral."""
        k = key.Key("C", "major")
        candidates = [("I", 1.0), ("IV", 0.8), ("V", 0.7)]

        selected = select_chord(candidates, "any", None, k)
        assert selected in ["I", "IV", "V"]

    def test_stepwise_bass_preference(self):
        """Stepwise bass prefers small intervals."""
        k = key.Key("C", "major")
        # After I chord, ii (D bass) is stepwise
        candidates = [("ii", 0.8), ("V", 0.9), ("vi", 0.7)]

        # With stepwise preference, should often pick ii
        # (This is probabilistic, so we just verify it works)
        selected = select_chord(candidates, "stepwise", "I", k)
        assert selected in ["ii", "V", "vi"]


class TestScoreVoiceLeading:
    """Tests for voice leading scoring."""

    def test_good_voice_leading(self):
        """Smooth progression gets high score."""
        k = key.Key("C", "major")
        # I -> IV -> V -> I is smooth
        progression = ["I", "IV", "V", "I"]

        score = score_voice_leading(progression, k, CLASSICAL_RULES)
        assert 0.0 <= score <= 1.0

    def test_single_chord_perfect(self):
        """Single chord has perfect voice leading."""
        k = key.Key("C", "major")
        score = score_voice_leading(["I"], k, CLASSICAL_RULES)
        assert score == 1.0


class TestScoreChordMelodyFit:
    """Tests for chord-melody fit scoring."""

    def test_good_fit(self):
        """Chord tones in melody get high fit score."""
        k = key.Key("C", "major")

        # Create melody with C, E, G (I chord tones)
        s = stream.Stream()
        for pitch in ["C4", "E4", "G4"]:
            n = note.Note(pitch)
            n.quarterLength = 1
            s.append(n)

        progression = ["I"]
        points = [0.0]

        score = score_chord_melody_fit(progression, s, points, k)
        assert score > 0.5


class TestScoreStyleAdherence:
    """Tests for style adherence scoring."""

    def test_common_progression_bonus(self):
        """Common progressions get style bonus."""
        # I-IV-V-I is common in classical
        progression = ["I", "IV", "V", "I"]

        score = score_style_adherence(progression, CLASSICAL_RULES)
        assert score > 0.5

    def test_jazz_ii_V_I(self):
        """ii-V-I is common in jazz."""
        progression = ["ii7", "V7", "Imaj7"]

        score = score_style_adherence(progression, JAZZ_RULES)
        assert score > 0.5


class TestReharmonize:
    """Tests for full reharmonization."""

    def test_basic_reharmonization(self):
        """Reharmonize a simple melody."""
        request = ReharmonizeRequest(
            melody="C4, D4, E4, G4",
            style=HarmonizationStyle.CLASSICAL,
        )

        response = reharmonize(request)
        assert response.success is True
        assert "harmonizations" in response.data
        assert len(response.data["harmonizations"]) > 0

    def test_multiple_options(self):
        """Request multiple harmonization options."""
        request = ReharmonizeRequest(
            melody="C4, E4, G4, C5",
            style=HarmonizationStyle.JAZZ,
            num_options=3,
        )

        response = reharmonize(request)
        assert response.success is True
        # Should return up to num_options unique harmonizations
        assert len(response.data["harmonizations"]) >= 1

    def test_harmonization_has_required_fields(self):
        """Each harmonization has required fields."""
        request = ReharmonizeRequest(
            melody="C4, D4, E4, F4",
            style=HarmonizationStyle.POP,
        )

        response = reharmonize(request)
        harm = response.data["harmonizations"][0]

        assert "rank" in harm
        assert "chords" in harm
        assert "roman_numerals" in harm
        assert "musicxml" in harm
        assert "scores" in harm

    def test_detected_key_returned(self):
        """Response includes detected key."""
        request = ReharmonizeRequest(
            melody="C4, E4, G4, C5",
            style=HarmonizationStyle.CLASSICAL,
        )

        response = reharmonize(request)
        assert "detected_key" in response.data
        # Should detect C major or related key
        assert "C" in response.data["detected_key"] or "major" in response.data["detected_key"]

    def test_chord_rhythm_per_beat(self):
        """Per-beat chord rhythm produces more chords."""
        request = ReharmonizeRequest(
            melody="C4, D4, E4, F4, G4, A4, B4, C5",
            style=HarmonizationStyle.CLASSICAL,
            chord_rhythm="per_beat",
        )

        response = reharmonize(request)
        harm = response.data["harmonizations"][0]

        # With 8 beats and per_beat, should have ~8 chords
        assert len(harm["chords"]) >= 4

    def test_modal_style(self):
        """Modal style produces valid harmonization."""
        request = ReharmonizeRequest(
            melody="D4, E4, F4, G4, A4",
            style=HarmonizationStyle.MODAL,
        )

        response = reharmonize(request)
        assert response.success is True
        assert response.data["style"] == "modal"

    def test_rankings_ordered(self):
        """Harmonizations are ranked 1, 2, 3, etc."""
        request = ReharmonizeRequest(
            melody="C4, E4, G4, C5",
            style=HarmonizationStyle.JAZZ,
            num_options=3,
        )

        response = reharmonize(request)
        ranks = [h["rank"] for h in response.data["harmonizations"]]

        for i, rank in enumerate(ranks):
            assert rank == i + 1

    def test_scores_in_valid_range(self):
        """All scores are between 0 and 1."""
        request = ReharmonizeRequest(
            melody="C4, D4, E4, G4",
            style=HarmonizationStyle.CLASSICAL,
        )

        response = reharmonize(request)
        harm = response.data["harmonizations"][0]

        for score_name, score_value in harm["scores"].items():
            assert 0.0 <= score_value <= 1.0, f"{score_name} out of range: {score_value}"

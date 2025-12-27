"""Reharmonization tools - generate chord progressions for melodies."""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

from music21 import chord, harmony, key, roman, stream

from composer_mcp.core.models import (
    ApiResponse,
    HarmonizationStyle,
    ReharmonizeRequest,
    Warning,
)
from composer_mcp.errors import (
    EmptyInputError,
    error_response,
    success_response,
)
from composer_mcp.core.validation import parse_input

if TYPE_CHECKING:
    from music21.stream import Stream
    from music21.key import Key


# === Style Rule Definitions ===

@dataclass
class StyleRules:
    """Rules for a harmonization style."""
    allowed_numerals: list[str]
    prefer_extensions: bool
    common_progressions: list[list[str]]
    cadence_patterns: dict[str, list[str]]
    substitutions: dict[str, dict[str, str]]
    avoid_parallel_fifths: bool = True
    avoid_parallel_octaves: bool = True
    prefer_root_position: bool = False
    allow_chromatic_approach: bool = False


CLASSICAL_RULES = StyleRules(
    allowed_numerals=["I", "ii", "iii", "IV", "V", "vi", "viio"],
    prefer_extensions=False,
    common_progressions=[
        ["I", "IV", "V", "I"],
        ["I", "vi", "IV", "V"],
        ["I", "ii", "V", "I"],
        ["I", "IV", "ii", "V"],
    ],
    cadence_patterns={
        "perfect": ["V", "I"],
        "plagal": ["IV", "I"],
        "half": ["ii", "V"],
        "deceptive": ["V", "vi"],
    },
    substitutions={},
    avoid_parallel_fifths=True,
    avoid_parallel_octaves=True,
)

JAZZ_RULES = StyleRules(
    allowed_numerals=["Imaj7", "ii7", "iii7", "IVmaj7", "V7", "vi7", "viio7"],
    prefer_extensions=True,
    common_progressions=[
        ["ii7", "V7", "Imaj7"],
        ["iii7", "vi7", "ii7", "V7"],
        ["Imaj7", "vi7", "ii7", "V7"],
        ["ii7", "V7", "iii7", "vi7"],
    ],
    cadence_patterns={
        "perfect": ["V7", "Imaj7"],
        "half": ["ii7", "V7"],
        "turnaround": ["Imaj7", "vi7", "ii7", "V7"],
    },
    substitutions={
        "V7": "bII7",  # Tritone sub
        "Imaj7": "vi7",  # Relative minor
        "IVmaj7": "ii7",  # Predominant sub
    },
    avoid_parallel_fifths=False,  # Less strict in jazz
    avoid_parallel_octaves=False,
    allow_chromatic_approach=True,
)

POP_RULES = StyleRules(
    allowed_numerals=["I", "ii", "IV", "V", "vi"],
    prefer_extensions=False,
    common_progressions=[
        ["I", "V", "vi", "IV"],  # The "4 chords"
        ["I", "IV", "vi", "V"],
        ["vi", "IV", "I", "V"],
        ["I", "IV", "I", "V"],
    ],
    cadence_patterns={
        "perfect": ["V", "I"],
        "plagal": ["IV", "I"],
    },
    substitutions={},
    prefer_root_position=True,
)

MODAL_RULES = StyleRules(
    allowed_numerals=["I", "II", "III", "IV", "V", "VI", "VII"],  # Modal numerals
    prefer_extensions=False,
    common_progressions=[
        ["I", "IV", "I"],  # Mixolydian vamp
        ["i", "VII", "VI"],  # Aeolian descent
        ["I", "II", "I"],  # Dorian color
    ],
    cadence_patterns={
        "modal": ["IV", "I"],  # Avoid V-I which sounds too tonal
        "plagal": ["IV", "I"],
    },
    substitutions={},
    avoid_parallel_fifths=False,
    avoid_parallel_octaves=False,
)

STYLE_RULES = {
    HarmonizationStyle.CLASSICAL: CLASSICAL_RULES,
    HarmonizationStyle.JAZZ: JAZZ_RULES,
    HarmonizationStyle.POP: POP_RULES,
    HarmonizationStyle.MODAL: MODAL_RULES,
}


# === Chord Point Detection ===

def get_chord_points(
    melody: "Stream",
    chord_rhythm: str,
    time_sig_numerator: int = 4,
) -> list[float]:
    """
    Determine where chord changes should occur.

    Args:
        melody: The melody stream
        chord_rhythm: "per_measure", "per_beat", or "per_half"
        time_sig_numerator: Beats per measure

    Returns:
        List of offsets where chords should be placed
    """
    # Get total length
    total_length = float(melody.duration.quarterLength)

    if chord_rhythm == "per_measure":
        # One chord per measure (every time_sig_numerator beats)
        step = float(time_sig_numerator)
    elif chord_rhythm == "per_half":
        # Two chords per measure
        step = float(time_sig_numerator) / 2
    else:  # per_beat
        step = 1.0

    points = []
    offset = 0.0
    while offset < total_length:
        points.append(offset)
        offset += step

    return points


def get_melody_notes_at(
    melody: "Stream",
    offset: float,
    duration: float = 1.0,
) -> list[str]:
    """
    Get melody note names sounding at a given offset.

    Args:
        melody: The melody stream
        offset: The time offset to check
        duration: How long a window to check

    Returns:
        List of pitch names (e.g., ["C", "E"])
    """
    notes = []
    for element in melody.recurse().notes:
        el_start = float(element.offset)
        el_end = el_start + float(element.duration.quarterLength)

        # Check if note overlaps with our window
        if el_start < offset + duration and el_end > offset:
            if hasattr(element, 'pitch'):
                notes.append(element.pitch.name)
            elif hasattr(element, 'pitches'):
                for p in element.pitches:
                    notes.append(p.name)

    return list(set(notes))  # Unique notes


# === Chord Candidate Generation ===

def get_chord_candidates(
    melody_notes: list[str],
    music_key: "Key",
    rules: StyleRules,
    previous_chord: Optional[str] = None,
    is_cadence: bool = False,
) -> list[tuple[str, float]]:
    """
    Generate chord candidates that fit the melody notes.

    Args:
        melody_notes: Pitch names in the melody at this point
        music_key: The key of the piece
        rules: Style rules to follow
        previous_chord: The previous chord (roman numeral)
        is_cadence: Whether this is a cadence point

    Returns:
        List of (roman_numeral, score) tuples
    """
    candidates = []

    for numeral_str in rules.allowed_numerals:
        try:
            rn = roman.RomanNumeral(numeral_str, music_key)
            chord_pitches = [p.name for p in rn.pitches]

            # Score based on melody fit
            score = 0.0

            # Melody notes that are chord tones get high score
            for note in melody_notes:
                if note in chord_pitches:
                    score += 1.0
                else:
                    # Check if it's a passing tone (less penalty)
                    score -= 0.3

            # Normalize by number of melody notes
            if melody_notes:
                score = score / len(melody_notes)
            else:
                score = 0.5  # Neutral if no melody notes

            # Bonus for common progressions
            if previous_chord:
                for prog in rules.common_progressions:
                    for i in range(len(prog) - 1):
                        if prog[i] == previous_chord and prog[i + 1] == numeral_str:
                            score += 0.3
                            break

            # Cadence handling
            if is_cadence:
                for cadence_type, pattern in rules.cadence_patterns.items():
                    if numeral_str in pattern:
                        score += 0.2

            # Slight randomness for variety
            score += random.uniform(-0.1, 0.1)

            candidates.append((numeral_str, score))

        except Exception:
            # Skip invalid roman numerals for this key
            continue

    return sorted(candidates, key=lambda x: x[1], reverse=True)


def select_chord(
    candidates: list[tuple[str, float]],
    bass_motion_pref: str,
    previous_chord: Optional[str],
    music_key: "Key",
) -> str:
    """
    Select a chord from candidates based on preferences.

    Args:
        candidates: Scored chord candidates
        bass_motion_pref: Bass motion preference
        previous_chord: Previous chord roman numeral
        music_key: The key

    Returns:
        Selected roman numeral string
    """
    if not candidates:
        return "I"  # Fallback

    # Weight by bass motion preference
    if bass_motion_pref != "any" and previous_chord:
        try:
            prev_rn = roman.RomanNumeral(previous_chord, music_key)
            prev_bass = prev_rn.bass().midi % 12

            weighted_candidates = []
            for numeral, score in candidates:
                rn = roman.RomanNumeral(numeral, music_key)
                curr_bass = rn.bass().midi % 12
                interval = abs(curr_bass - prev_bass)

                bonus = 0.0
                if bass_motion_pref == "stepwise" and interval <= 2:
                    bonus = 0.2
                elif bass_motion_pref == "fifths" and interval in [5, 7]:
                    bonus = 0.2
                elif bass_motion_pref == "pedal" and interval == 0:
                    bonus = 0.3

                weighted_candidates.append((numeral, score + bonus))

            candidates = sorted(weighted_candidates, key=lambda x: x[1], reverse=True)
        except Exception:
            pass

    # Select from top candidates with some randomness
    top_candidates = candidates[:3] if len(candidates) >= 3 else candidates

    # Weighted random selection
    total = sum(max(0.1, score) for _, score in top_candidates)
    r = random.random() * total
    cumulative = 0
    for numeral, score in top_candidates:
        cumulative += max(0.1, score)
        if r <= cumulative:
            return numeral

    return candidates[0][0]


# === Voice Leading Scoring ===

def score_voice_leading(
    progression: list[str],
    music_key: "Key",
    rules: StyleRules,
) -> float:
    """
    Score a chord progression for voice leading quality.

    Args:
        progression: List of roman numeral strings
        music_key: The key
        rules: Style rules

    Returns:
        Score from 0.0 to 1.0
    """
    if len(progression) < 2:
        return 1.0

    score = 1.0

    for i in range(len(progression) - 1):
        try:
            curr = roman.RomanNumeral(progression[i], music_key)
            next_chord = roman.RomanNumeral(progression[i + 1], music_key)

            curr_pitches = [p.midi % 12 for p in curr.pitches]
            next_pitches = [p.midi % 12 for p in next_chord.pitches]

            # Check for parallel fifths
            if rules.avoid_parallel_fifths:
                for j, cp in enumerate(curr_pitches[:-1]):
                    for k, cp2 in enumerate(curr_pitches[j + 1:], j + 1):
                        if (cp2 - cp) % 12 == 7:  # Perfect fifth
                            # Check if same interval in next chord
                            if j < len(next_pitches) and k < len(next_pitches):
                                if (next_pitches[k] - next_pitches[j]) % 12 == 7:
                                    score -= 0.1

            # Check for parallel octaves
            if rules.avoid_parallel_octaves:
                for j, cp in enumerate(curr_pitches[:-1]):
                    for k, cp2 in enumerate(curr_pitches[j + 1:], j + 1):
                        if cp == cp2:  # Unison/octave
                            if j < len(next_pitches) and k < len(next_pitches):
                                if next_pitches[j] == next_pitches[k]:
                                    score -= 0.1

            # Reward smooth voice leading (small intervals)
            if len(curr_pitches) == len(next_pitches):
                total_motion = sum(
                    min(abs(c - n), 12 - abs(c - n))
                    for c, n in zip(curr_pitches, next_pitches)
                )
                avg_motion = total_motion / len(curr_pitches)
                if avg_motion <= 2:
                    score += 0.05
                elif avg_motion > 4:
                    score -= 0.05

        except Exception:
            continue

    return max(0.0, min(1.0, score))


def score_chord_melody_fit(
    progression: list[str],
    melody: "Stream",
    chord_points: list[float],
    music_key: "Key",
) -> float:
    """
    Score how well chords fit the melody notes.

    Args:
        progression: List of roman numeral strings
        melody: The melody stream
        chord_points: Offsets where chords occur
        music_key: The key

    Returns:
        Score from 0.0 to 1.0
    """
    if not progression or not chord_points:
        return 0.5

    total_fit = 0.0
    count = 0

    for i, (numeral, offset) in enumerate(zip(progression, chord_points)):
        try:
            rn = roman.RomanNumeral(numeral, music_key)
            chord_pitches = [p.name for p in rn.pitches]

            # Get duration until next chord
            if i < len(chord_points) - 1:
                duration = chord_points[i + 1] - offset
            else:
                duration = 4.0  # Assume one measure

            melody_notes = get_melody_notes_at(melody, offset, duration)

            if melody_notes:
                matches = sum(1 for n in melody_notes if n in chord_pitches)
                total_fit += matches / len(melody_notes)
                count += 1

        except Exception:
            continue

    return total_fit / count if count > 0 else 0.5


def score_style_adherence(
    progression: list[str],
    rules: StyleRules,
) -> float:
    """
    Score how well progression follows style conventions.

    Args:
        progression: List of roman numeral strings
        rules: Style rules

    Returns:
        Score from 0.0 to 1.0
    """
    score = 0.5  # Base score

    # Check for common progression patterns
    prog_str = " ".join(progression)
    for common in rules.common_progressions:
        common_str = " ".join(common)
        if common_str in prog_str:
            score += 0.2

    # Check cadence at end
    if len(progression) >= 2:
        final_two = progression[-2:]
        for pattern in rules.cadence_patterns.values():
            if len(pattern) >= 2 and final_two == pattern[-2:]:
                score += 0.15
                break

    return min(1.0, score)


# === Main Reharmonize Function ===

def reharmonize(request: ReharmonizeRequest) -> ApiResponse:
    """
    Generate alternative chord progressions for a melody.

    Args:
        request: Reharmonization parameters

    Returns:
        ApiResponse with harmonization options
    """
    try:
        # Parse melody
        melody = parse_input(request.melody, request.input_format)

        if not list(melody.recurse().notes):
            raise EmptyInputError("Melody contains no notes", field="melody")

        # Analyze key
        detected_key = melody.analyze('key')

        # Get style rules
        rules = STYLE_RULES.get(request.style, CLASSICAL_RULES)

        # Determine if extensions should be allowed
        allow_extended = request.allow_extended
        if allow_extended is None:
            allow_extended = rules.prefer_extensions

        # Get time signature
        time_sigs = melody.getTimeSignatures()
        time_sig_num = time_sigs[0].numerator if time_sigs else 4

        # Get chord points
        chord_points = get_chord_points(melody, request.chord_rhythm, time_sig_num)

        # Generate multiple harmonizations
        harmonizations = []
        num_attempts = request.num_options * 5  # Generate extra, keep best

        for attempt in range(num_attempts):
            # Seed for variety across attempts
            random.seed(attempt * 1000 + hash(request.melody) % 10000)

            progression = []

            for i, offset in enumerate(chord_points):
                duration = (
                    chord_points[i + 1] - offset
                    if i < len(chord_points) - 1
                    else float(time_sig_num)
                )

                melody_notes = get_melody_notes_at(melody, offset, duration)
                is_cadence = i >= len(chord_points) - 2

                candidates = get_chord_candidates(
                    melody_notes=melody_notes,
                    music_key=detected_key,
                    rules=rules,
                    previous_chord=progression[-1] if progression else None,
                    is_cadence=is_cadence,
                )

                selected = select_chord(
                    candidates=candidates,
                    bass_motion_pref=request.bass_motion,
                    previous_chord=progression[-1] if progression else None,
                    music_key=detected_key,
                )

                progression.append(selected)

            # Score this harmonization
            vl_score = score_voice_leading(progression, detected_key, rules)
            cm_score = score_chord_melody_fit(progression, melody, chord_points, detected_key)
            style_score = score_style_adherence(progression, rules)
            overall = (vl_score + cm_score + style_score) / 3

            # Convert to chord symbols
            chord_symbols = []
            for numeral in progression:
                try:
                    rn = roman.RomanNumeral(numeral, detected_key)
                    symbol = harmony.chordSymbolFromChord(chord.Chord(rn.pitches))
                    chord_symbols.append(symbol.figure if symbol else numeral)
                except Exception:
                    chord_symbols.append(numeral)

            harmonizations.append({
                "progression": progression,
                "chord_symbols": chord_symbols,
                "scores": {
                    "voice_leading": round(vl_score, 2),
                    "chord_melody_fit": round(cm_score, 2),
                    "style_adherence": round(style_score, 2),
                    "overall": round(overall, 2),
                },
            })

        # Sort by overall score and keep unique progressions
        seen = set()
        unique_harmonizations = []
        for h in sorted(harmonizations, key=lambda x: x["scores"]["overall"], reverse=True):
            prog_key = tuple(h["progression"])
            if prog_key not in seen:
                seen.add(prog_key)
                unique_harmonizations.append(h)
            if len(unique_harmonizations) >= request.num_options:
                break

        # Build response
        result_harmonizations = []
        for rank, h in enumerate(unique_harmonizations, 1):
            # Build MusicXML with chords
            harm_stream = stream.Stream()
            harm_stream.append(detected_key)

            for i, (offset, numeral) in enumerate(zip(chord_points, h["progression"])):
                try:
                    rn = roman.RomanNumeral(numeral, detected_key)
                    c = chord.Chord(rn.pitches)
                    c.offset = offset
                    if i < len(chord_points) - 1:
                        c.duration.quarterLength = chord_points[i + 1] - offset
                    else:
                        c.duration.quarterLength = float(time_sig_num)
                    harm_stream.append(c)
                except Exception:
                    pass

            from composer_mcp.core.validation import stream_to_musicxml
            musicxml = stream_to_musicxml(harm_stream)

            result_harmonizations.append({
                "rank": rank,
                "chords": h["chord_symbols"],
                "roman_numerals": h["progression"],
                "musicxml": musicxml,
                "scores": h["scores"],
            })

        response_data = {
            "detected_key": str(detected_key),
            "chord_rhythm": request.chord_rhythm,
            "style": request.style.value,
            "harmonizations": result_harmonizations,
        }

        return success_response(response_data)

    except Exception as e:
        return error_response(e)

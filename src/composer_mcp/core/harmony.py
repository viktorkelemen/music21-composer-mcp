"""Harmony tools - chord voicing and reharmonization."""

from __future__ import annotations

from typing import TYPE_CHECKING

from music21 import chord, harmony, pitch

from composer_mcp.core.models import (
    ApiResponse,
    ChordResponseData,
    RealizeChordRequest,
    VoicingAnalysis,
    VoicingData,
    VoicingStyle,
)
from composer_mcp.errors import InvalidChordSymbolError, success_response

if TYPE_CHECKING:
    from music21.pitch import Pitch


# Instrument range constraints
INSTRUMENT_RANGES = {
    "piano": {"low": "A0", "high": "C8", "max_notes": 10},
    "guitar": {"low": "E2", "high": "E6", "max_notes": 6},
    "satb": {"low": "E2", "high": "A5", "max_notes": 4},
    "strings": {"low": "C2", "high": "E6", "max_notes": 4},
}


def parse_chord_symbol(symbol: str) -> harmony.ChordSymbol:
    """Parse a chord symbol string into a music21 ChordSymbol."""
    try:
        return harmony.ChordSymbol(symbol)
    except Exception as e:
        raise InvalidChordSymbolError(
            f"Could not parse chord symbol: {symbol}",
            field="chord_symbol",
            suggestions=["Cmaj7", "Dm7", "G7", "Am", "F#dim7"],
        ) from e


def close_voicing(pitches: list["Pitch"], inversion: int = 0) -> list["Pitch"]:
    """
    Create close position voicing.

    Notes stacked within an octave, minimal spacing.
    """
    if not pitches:
        return []

    # Rotate for inversion
    pitches = list(pitches)
    if inversion > 0 and inversion < len(pitches):
        pitches = pitches[inversion:] + pitches[:inversion]

    # Stack within octave from bass
    result = [pitches[0]]
    for p in pitches[1:]:
        new_p = pitch.Pitch(p.nameWithOctave)
        while new_p.midi <= result[-1].midi:
            new_p.octave += 1
        result.append(new_p)

    return result


def open_voicing(pitches: list["Pitch"], inversion: int = 0) -> list["Pitch"]:
    """
    Create open position voicing.

    Spread notes across more than an octave.
    """
    close = close_voicing(pitches, inversion)
    if len(close) < 4:
        return close

    # Move every other note up an octave
    result = []
    for i, p in enumerate(close):
        new_p = pitch.Pitch(p.nameWithOctave)
        if i % 2 == 1 and i < len(close) - 1:
            new_p.octave += 1
        result.append(new_p)

    return sorted(result, key=lambda x: x.midi)


def drop2_voicing(pitches: list["Pitch"]) -> list["Pitch"]:
    """
    Create drop 2 voicing.

    Take close voicing, drop 2nd-from-top note an octave.
    """
    close = close_voicing(pitches, 0)
    if len(close) < 4:
        return close

    result = list(close)
    # Drop 2nd from top (index -2) an octave
    result[-2] = pitch.Pitch(result[-2].nameWithOctave)
    result[-2].octave -= 1

    return sorted(result, key=lambda x: x.midi)


def drop3_voicing(pitches: list["Pitch"]) -> list["Pitch"]:
    """
    Create drop 3 voicing.

    Take close voicing, drop 3rd-from-top note an octave.
    """
    close = close_voicing(pitches, 0)
    if len(close) < 4:
        return close

    result = list(close)
    # Drop 3rd from top (index -3) an octave
    if len(result) >= 3:
        result[-3] = pitch.Pitch(result[-3].nameWithOctave)
        result[-3].octave -= 1

    return sorted(result, key=lambda x: x.midi)


def quartal_voicing(root: "Pitch") -> list["Pitch"]:
    """
    Create quartal voicing.

    Stack in 4ths instead of 3rds.
    """
    result = [root]
    current = root

    for interval in ["P4", "P4", "P4"]:
        current = current.transpose(interval)
        result.append(current)

    return result


def apply_range_constraints(
    pitches: list["Pitch"],
    range_low: str | None,
    range_high: str | None,
    instrument: str,
) -> list["Pitch"]:
    """Adjust pitches to fit within range constraints."""
    constraints = INSTRUMENT_RANGES.get(instrument, INSTRUMENT_RANGES["piano"])

    low = pitch.Pitch(range_low) if range_low else pitch.Pitch(constraints["low"])
    high = pitch.Pitch(range_high) if range_high else pitch.Pitch(constraints["high"])

    result = []
    for p in pitches:
        new_p = pitch.Pitch(p.nameWithOctave)

        # Shift octaves to fit in range
        while new_p.midi < low.midi:
            new_p.octave += 1
        while new_p.midi > high.midi:
            new_p.octave -= 1

        # Only include if within range
        if low.midi <= new_p.midi <= high.midi:
            result.append(new_p)

    # Limit to max notes for instrument
    max_notes = constraints["max_notes"]
    if len(result) > max_notes:
        result = result[:max_notes]

    return sorted(result, key=lambda x: x.midi)


def get_intervals_from_bass(pitches: list["Pitch"]) -> list[str]:
    """Get interval names from bass note to each upper note."""
    if len(pitches) < 2:
        return []

    from music21 import interval

    bass = pitches[0]
    intervals = []

    for p in pitches[1:]:
        ivl = interval.Interval(bass, p)
        intervals.append(ivl.simpleName)

    return intervals


def realize_chord(request: RealizeChordRequest) -> ApiResponse:
    """
    Generate specific voicings for chord symbols.

    Args:
        request: Chord realization parameters

    Returns:
        ApiResponse with voicing data
    """
    # Parse chord symbol
    cs = parse_chord_symbol(request.chord_symbol)
    pitches = list(cs.pitches)

    if not pitches:
        raise InvalidChordSymbolError(
            f"Chord symbol '{request.chord_symbol}' produced no pitches",
            field="chord_symbol",
        )

    # Handle slash chord (bass note override)
    if request.bass_note:
        bass = pitch.Pitch(request.bass_note)
        # Remove if already in chord, then add at bottom
        pitches = [p for p in pitches if p.name != bass.name]
        pitches.insert(0, bass)

    # Apply voicing style
    if request.voicing_style == VoicingStyle.CLOSE:
        voiced = close_voicing(pitches, request.inversion)
    elif request.voicing_style == VoicingStyle.OPEN:
        voiced = open_voicing(pitches, request.inversion)
    elif request.voicing_style == VoicingStyle.DROP2:
        voiced = drop2_voicing(pitches)
    elif request.voicing_style == VoicingStyle.DROP3:
        voiced = drop3_voicing(pitches)
    elif request.voicing_style == VoicingStyle.QUARTAL:
        voiced = quartal_voicing(pitches[0])
    else:
        voiced = close_voicing(pitches, request.inversion)

    # Apply range constraints
    voiced = apply_range_constraints(
        voiced,
        request.range_low,
        request.range_high,
        request.instrument,
    )

    # Build chord for MusicXML export
    c = chord.Chord(voiced)

    from composer_mcp.core.validation import stream_to_musicxml
    from music21 import stream

    s = stream.Stream()
    s.append(c)
    musicxml = stream_to_musicxml(s)

    # Determine chord quality
    chord_quality = cs.chordKind or "unknown"

    # Build response
    response_data = ChordResponseData(
        voicing=VoicingData(
            notes=[p.nameWithOctave for p in voiced],
            midi_pitches=[int(p.midi) for p in voiced],
            musicxml=musicxml,
        ),
        analysis=VoicingAnalysis(
            chord_quality=chord_quality,
            voicing_style=request.voicing_style.value,
            inversion=request.inversion,
            intervals_from_bass=get_intervals_from_bass(voiced),
        ),
        alternatives=[],
    )

    # Generate alternatives
    alt_styles = [vs for vs in VoicingStyle if vs != request.voicing_style]
    for style in alt_styles[:2]:  # Include 2 alternatives
        if style == VoicingStyle.CLOSE:
            alt_voiced = close_voicing(pitches, 0)
        elif style == VoicingStyle.DROP2:
            alt_voiced = drop2_voicing(pitches)
        elif style == VoicingStyle.DROP3:
            alt_voiced = drop3_voicing(pitches)
        else:
            continue

        alt_voiced = apply_range_constraints(
            alt_voiced, request.range_low, request.range_high, request.instrument
        )

        response_data.alternatives.append({
            "notes": [p.nameWithOctave for p in alt_voiced],
            "style": style.value,
        })

    return success_response(response_data)

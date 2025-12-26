"""Input validation and format detection."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from music21 import converter, stream

from composer_mcp.core.models import InputFormat
from composer_mcp.errors import EmptyInputError, ParseError

if TYPE_CHECKING:
    from music21.stream import Stream


# Format detection patterns
MUSICXML_PATTERN = re.compile(r"^\s*(<\?xml|<score|<part|<!DOCTYPE)")
ABC_PATTERN = re.compile(r"^\s*[A-Z]:")
NOTES_PATTERN = re.compile(r"^\s*[A-Ga-g][#b]?\d")


def detect_format(input_string: str) -> InputFormat:
    """
    Detect the format of a musical input string.

    Returns:
        InputFormat enum value

    Raises:
        ParseError: If format cannot be detected
    """
    stripped = input_string.strip()

    if not stripped:
        raise EmptyInputError("Input is empty")

    # MusicXML: starts with XML declaration or root element
    if MUSICXML_PATTERN.match(stripped):
        return InputFormat.MUSICXML

    # ABC: starts with field (X:, T:, M:, K:, etc.)
    if ABC_PATTERN.match(stripped):
        return InputFormat.ABC

    # Note list: comma or space separated pitch names
    if NOTES_PATTERN.match(stripped):
        return InputFormat.NOTES

    raise ParseError(
        "Could not detect input format. Please specify format explicitly.",
        suggestions=["musicxml", "abc", "notes"],
    )


def parse_note_list(note_string: str) -> "Stream":
    """
    Parse a simple note list into a music21 Stream.

    Format: "C4:q, D4:q, E4:h" or "C4 D4 E4 G4"

    Duration codes:
        w = whole, h = half, q = quarter, e = eighth, s = sixteenth
        d suffix = dotted (can stack)

    Returns:
        music21 Stream with parsed notes
    """
    from music21 import duration, note, pitch

    DURATION_MAP = {
        "w": 4.0,
        "h": 2.0,
        "q": 1.0,
        "e": 0.5,
        "s": 0.25,
    }

    s = stream.Stream()

    # Split by comma or whitespace
    tokens = re.split(r"[,\s]+", note_string.strip())

    for token in tokens:
        if not token:
            continue

        # Split pitch and duration
        if ":" in token:
            pitch_str, dur_str = token.split(":", 1)
        else:
            pitch_str = token
            dur_str = "q"  # default quarter note

        # Parse pitch
        try:
            p = pitch.Pitch(pitch_str)
        except Exception as e:
            raise ParseError(f"Invalid pitch: {pitch_str}") from e

        # Parse duration
        base_dur = DURATION_MAP.get(dur_str[0], 1.0)
        dots = dur_str.count("d")
        dur_value = base_dur
        for _ in range(dots):
            dur_value *= 1.5

        n = note.Note(p)
        n.duration = duration.Duration(dur_value)
        s.append(n)

    return s


def parse_input(input_string: str, input_format: InputFormat | None = None) -> "Stream":
    """
    Parse musical input into a music21 Stream.

    Args:
        input_string: The musical content
        input_format: Explicit format, or None for auto-detection

    Returns:
        music21 Stream

    Raises:
        ParseError: If parsing fails
    """
    if not input_string or not input_string.strip():
        raise EmptyInputError("Input is empty")

    # Detect format if not specified
    if input_format is None:
        input_format = detect_format(input_string)

    try:
        if input_format == InputFormat.MUSICXML:
            return converter.parse(input_string)

        elif input_format == InputFormat.ABC:
            return converter.parse(input_string, format="abc")

        elif input_format == InputFormat.NOTES:
            return parse_note_list(input_string)

        else:
            raise ParseError(f"Unknown format: {input_format}")

    except EmptyInputError:
        raise
    except ParseError:
        raise
    except Exception as e:
        raise ParseError(f"Failed to parse input: {e}") from e


def stream_to_musicxml(s: "Stream") -> str:
    """Convert a music21 Stream to MusicXML string."""
    from music21 import musicxml

    exporter = musicxml.m21ToXml.GeneralObjectExporter(s)
    return exporter.parse().decode("utf-8")


def stream_to_abc(s: "Stream") -> str:
    """Convert a music21 Stream to ABC notation."""
    from music21 import abcFormat

    # music21's ABC export is limited, this is a best-effort
    try:
        return abcFormat.translate.streamToABCText(s)
    except (AttributeError, TypeError, ValueError):
        # Fallback: return a minimal representation
        notes = [n.nameWithOctave for n in s.recurse().notes]
        return " ".join(notes)

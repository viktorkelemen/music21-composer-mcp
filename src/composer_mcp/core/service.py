"""Core composition service - protocol independent."""

from __future__ import annotations

import base64
import random
from io import BytesIO
from typing import TYPE_CHECKING, Optional

from music21 import midi, tempo

from composer_mcp.core.models import (
    ApiResponse,
    ExportMidiRequest,
    MidiData,
    MidiMetadata,
    MidiResponseData,
    Warning,
)
from composer_mcp.core.validation import parse_input, stream_to_abc
from composer_mcp.errors import success_response, error_response

if TYPE_CHECKING:
    from music21.stream import Stream


class CompositionService:
    """
    Core composition service providing all tool implementations.

    This class is protocol-independent and can be used by any adapter
    (MCP, HTTP, CLI).
    """

    def __init__(self):
        # Pre-import music21 to warm up
        import music21  # noqa: F401

    def export_midi(self, request: ExportMidiRequest) -> ApiResponse:
        """
        Export a musical stream to MIDI format.

        Args:
            request: Export parameters

        Returns:
            ApiResponse with MIDI data
        """
        try:
            # Parse input
            stream = parse_input(request.stream, request.input_format)

            # Set tempo
            stream.insert(0, tempo.MetronomeMark(number=request.tempo))

            # Apply humanization if requested
            if request.humanize:
                stream = self._humanize_stream(
                    stream,
                    amount=request.humanize_amount,
                    velocity_curve=request.velocity_curve,
                )

            # Export to MIDI
            midi_file = midi.translate.streamToMidiFile(stream)
            midi_bytes = midi_file.writestr()
            midi_base64 = base64.b64encode(midi_bytes).decode("utf-8")

            # Calculate duration
            duration_seconds = float(stream.duration.quarterLength) * (60.0 / request.tempo)

            # Count tracks
            track_count = len(stream.parts) if hasattr(stream, "parts") and stream.parts else 1

            # Get metadata
            measures = len(stream.getElementsByClass("Measure")) or 1
            time_sig = stream.getTimeSignatures()[0] if stream.getTimeSignatures() else None
            time_sig_str = f"{time_sig.numerator}/{time_sig.denominator}" if time_sig else "4/4"

            key_sig = stream.analyze("key") if stream.notes else None
            key_sig_str = str(key_sig) if key_sig else None

            note_count = len(list(stream.recurse().notes))

            # Build response data
            response_data = MidiResponseData(
                midi=MidiData(
                    base64=midi_base64,
                    duration_seconds=round(duration_seconds, 2),
                    track_count=track_count,
                    tempo=request.tempo,
                ),
                metadata=MidiMetadata(
                    measures=measures,
                    time_signature=time_sig_str,
                    key_signature=key_sig_str,
                    note_count=note_count,
                ),
                abc=stream_to_abc(stream) if request.include_abc else None,
            )

            return success_response(response_data)

        except Exception as e:
            return error_response(e)

    def _humanize_stream(
        self,
        stream: "Stream",
        amount: float = 0.3,
        velocity_curve: str = "flat",
        seed: Optional[int] = None,
    ) -> "Stream":
        """
        Add human-like imperfections to a stream.

        Args:
            stream: The music21 stream to humanize
            amount: Intensity 0.0-1.0
            velocity_curve: "flat", "dynamic", "crescendo", "diminuendo"
            seed: Random seed for reproducibility

        Returns:
            Humanized stream (modified in place)
        """
        rng = random.Random(seed)

        # Calculate jitter amounts based on intensity
        timing_jitter_ql = 0.05 * amount  # quarter-length units
        velocity_jitter = int(25 * amount)  # max ±8 at 0.3
        duration_jitter = 0.15 * amount  # max ±5% at 0.3

        notes = list(stream.recurse().notes)
        total_notes = len(notes)

        for i, note in enumerate(notes):
            # Timing jitter (small offset to note start)
            # Clamp to avoid negative offsets which break MIDI export
            if hasattr(note, "offset"):
                new_offset = note.offset + rng.gauss(0, timing_jitter_ql)
                note.offset = max(0, new_offset)

            # Velocity variation
            if hasattr(note, "volume") and note.volume:
                base_velocity = note.volume.velocity or 64

                # Apply velocity curve
                if velocity_curve == "crescendo" and total_notes > 1:
                    curve_factor = i / (total_notes - 1)
                    base_velocity = int(50 + curve_factor * 77)
                elif velocity_curve == "diminuendo" and total_notes > 1:
                    curve_factor = 1 - (i / (total_notes - 1))
                    base_velocity = int(50 + curve_factor * 77)
                elif velocity_curve == "dynamic":
                    # Add more variation for dynamic
                    velocity_jitter = int(40 * amount)

                # Add random variation
                velocity = base_velocity + rng.randint(-velocity_jitter, velocity_jitter)
                velocity = max(1, min(127, velocity))
                note.volume.velocity = velocity

            # Duration jitter
            if hasattr(note, "duration") and note.duration:
                factor = 1 + rng.uniform(-duration_jitter, duration_jitter)
                note.duration.quarterLength *= factor

        return stream


# Global service instance
_service: Optional[CompositionService] = None


def get_service() -> CompositionService:
    """Get or create the global service instance."""
    global _service
    if _service is None:
        _service = CompositionService()
    return _service

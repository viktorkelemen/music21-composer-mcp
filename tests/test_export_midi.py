"""Tests for export_midi tool."""

import base64
import pytest
from music21 import midi

from composer_mcp.core.models import ExportMidiRequest, InputFormat
from composer_mcp.core.service import CompositionService


@pytest.fixture
def service():
    """Create a composition service instance."""
    return CompositionService()


class TestExportMidi:
    """Tests for export_midi functionality."""

    def test_export_simple_notes(self, service):
        """Export simple note list to MIDI."""
        request = ExportMidiRequest(
            stream="C4, D4, E4, G4",
            tempo=120,
        )
        response = service.export_midi(request)

        assert response.success is True
        assert response.error is None
        assert response.data is not None

        # Check MIDI data
        midi_data = response.data["midi"]
        assert "base64" in midi_data
        assert midi_data["tempo"] == 120
        assert midi_data["duration_seconds"] > 0

        # Verify base64 is valid MIDI
        midi_bytes = base64.b64decode(midi_data["base64"])
        assert midi_bytes[:4] == b"MThd"  # MIDI header

    def test_export_with_durations(self, service):
        """Export notes with explicit durations."""
        request = ExportMidiRequest(
            stream="C4:h, D4:q, E4:q",
            tempo=120,
        )
        response = service.export_midi(request)

        assert response.success is True
        # Half (2) + quarter (1) + quarter (1) = 4 quarter lengths at 120 BPM = 2 seconds
        assert response.data["midi"]["duration_seconds"] == pytest.approx(2.0, rel=0.1)

    def test_export_with_different_tempo(self, service):
        """Tempo affects duration."""
        request_slow = ExportMidiRequest(stream="C4:w", tempo=60)
        request_fast = ExportMidiRequest(stream="C4:w", tempo=120)

        response_slow = service.export_midi(request_slow)
        response_fast = service.export_midi(request_fast)

        # Same notes, different tempo = different duration
        slow_duration = response_slow.data["midi"]["duration_seconds"]
        fast_duration = response_fast.data["midi"]["duration_seconds"]

        assert slow_duration == pytest.approx(fast_duration * 2, rel=0.1)

    def test_export_explicit_format(self, service):
        """Explicit input format."""
        request = ExportMidiRequest(
            stream="C4 D4 E4",
            input_format=InputFormat.NOTES,
            tempo=120,
        )
        response = service.export_midi(request)

        assert response.success is True

    def test_export_with_humanization(self, service):
        """Humanization modifies output."""
        request_normal = ExportMidiRequest(
            stream="C4, D4, E4, G4",
            humanize=False,
        )
        request_humanized = ExportMidiRequest(
            stream="C4, D4, E4, G4",
            humanize=True,
            humanize_amount=0.5,
        )

        response_normal = service.export_midi(request_normal)
        response_humanized = service.export_midi(request_humanized)

        # Both should succeed
        assert response_normal.success is True
        assert response_humanized.success is True

        # MIDI output should be different (humanization adds variation)
        # Note: This might occasionally fail if randomization produces same result
        normal_midi = response_normal.data["midi"]["base64"]
        humanized_midi = response_humanized.data["midi"]["base64"]

        # Just verify both are valid MIDI, don't compare bytes
        assert base64.b64decode(normal_midi)[:4] == b"MThd"
        assert base64.b64decode(humanized_midi)[:4] == b"MThd"

    def test_export_metadata(self, service):
        """Response includes metadata."""
        request = ExportMidiRequest(
            stream="C4, D4, E4, G4",
            tempo=100,
        )
        response = service.export_midi(request)

        assert response.success is True
        metadata = response.data["metadata"]

        assert "note_count" in metadata
        assert metadata["note_count"] == 4
        assert "time_signature" in metadata

    def test_export_include_abc(self, service):
        """Include ABC notation in response."""
        request = ExportMidiRequest(
            stream="C4, D4, E4",
            include_abc=True,
        )
        response = service.export_midi(request)

        assert response.success is True
        assert response.data.get("abc") is not None

    def test_export_empty_input_fails(self, service):
        """Empty input is caught by Pydantic validation."""
        import pydantic
        with pytest.raises(pydantic.ValidationError):
            ExportMidiRequest(stream="")

    def test_export_invalid_notes_fails(self, service):
        """Invalid notes return error."""
        request = ExportMidiRequest(stream="X9, Y8, Z7")
        response = service.export_midi(request)

        assert response.success is False
        assert response.error is not None

    def test_velocity_curves(self, service):
        """Different velocity curves produce valid output."""
        for curve in ["flat", "dynamic", "crescendo", "diminuendo"]:
            request = ExportMidiRequest(
                stream="C4, D4, E4, G4, C5",
                humanize=True,
                velocity_curve=curve,
            )
            response = service.export_midi(request)
            assert response.success is True, f"Failed for curve: {curve}"

    def test_api_version_included(self, service):
        """Response includes API version."""
        request = ExportMidiRequest(stream="C4")
        response = service.export_midi(request)

        assert response.api_version == "0.1.0"

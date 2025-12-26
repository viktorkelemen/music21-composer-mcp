"""Tests for HTTP adapter."""

import pytest
from fastapi.testclient import TestClient

from composer_mcp.adapters.http_adapter import app


@pytest.fixture
def client():
    """Create a test client."""
    return TestClient(app)


class TestHealthCheck:
    """Tests for health check endpoint."""

    def test_health_check(self, client):
        """Health check returns healthy status."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "version" in data


class TestExportMidiEndpoint:
    """Tests for /export_midi endpoint."""

    def test_export_simple_notes(self, client):
        """Export simple notes via HTTP."""
        response = client.post(
            "/export_midi",
            json={
                "stream": "C4, D4, E4, G4",
                "tempo": 120,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "midi" in data["data"]
        assert "base64" in data["data"]["midi"]

    def test_export_with_all_options(self, client):
        """Export with all options specified."""
        response = client.post(
            "/export_midi",
            json={
                "stream": "C4:q, D4:q, E4:h",
                "input_format": "notes",
                "tempo": 100,
                "humanize": True,
                "humanize_amount": 0.3,
                "velocity_curve": "crescendo",
                "include_abc": True,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["abc"] is not None

    def test_export_empty_stream_fails(self, client):
        """Empty stream returns 400."""
        response = client.post(
            "/export_midi",
            json={"stream": ""},
        )
        # Pydantic validation catches empty string
        assert response.status_code == 422

    def test_export_invalid_tempo(self, client):
        """Invalid tempo returns 422."""
        response = client.post(
            "/export_midi",
            json={
                "stream": "C4, D4",
                "tempo": 500,  # Max is 300
            },
        )
        assert response.status_code == 422


class TestGenerateMelodyEndpoint:
    """Tests for /generate_melody endpoint."""

    def test_generate_melody_basic(self, client):
        """Generate a simple melody."""
        response = client.post(
            "/generate_melody",
            json={
                "key": "C major",
                "length_measures": 2,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "melody" in data["data"]
        assert "metadata" in data["data"]
        assert data["data"]["metadata"]["measures"] == 2

    def test_generate_melody_with_constraints(self, client):
        """Generate melody with contour and range constraints."""
        response = client.post(
            "/generate_melody",
            json={
                "key": "D dorian",
                "length_measures": 4,
                "contour": "arch",
                "range_low": "D4",
                "range_high": "D5",
                "rhythmic_density": "sparse",
                "seed": 42,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["metadata"]["key"] == "D dorian"
        assert data["data"]["metadata"]["seed_used"] == 42

    def test_generate_melody_invalid_key(self, client):
        """Invalid key format returns 422."""
        response = client.post(
            "/generate_melody",
            json={
                "key": "invalid",
                "length_measures": 4,
            },
        )
        assert response.status_code == 422


class TestRealizeChordEndpoint:
    """Tests for /realize_chord endpoint."""

    def test_realize_chord_basic(self, client):
        """Realize a simple chord."""
        response = client.post(
            "/realize_chord",
            json={"chord_symbol": "Cmaj7"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "voicing" in data["data"]
        assert "analysis" in data["data"]
        assert len(data["data"]["voicing"]["notes"]) > 0

    def test_realize_chord_with_style(self, client):
        """Realize chord with drop2 voicing."""
        response = client.post(
            "/realize_chord",
            json={
                "chord_symbol": "Dm7",
                "voicing_style": "drop2",
                "instrument": "guitar",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["analysis"]["voicing_style"] == "drop2"

    def test_realize_chord_slash(self, client):
        """Realize chord with custom bass note."""
        response = client.post(
            "/realize_chord",
            json={
                "chord_symbol": "G7",
                "bass_note": "B2",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        # Bass note should be the lowest
        notes = data["data"]["voicing"]["notes"]
        assert notes[0].startswith("B")


class TestNotImplementedEndpoints:
    """Tests for not-yet-implemented endpoints."""

    def test_transform_phrase_not_implemented(self, client):
        """transform_phrase returns not implemented."""
        response = client.post(
            "/transform_phrase",
            json={
                "input_stream": "C4, D4, E4",
                "transformation": "sequence",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False

    def test_reharmonize_not_implemented(self, client):
        """reharmonize returns not implemented."""
        response = client.post(
            "/reharmonize",
            json={
                "melody": "C4, D4, E4",
                "style": "jazz",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False

    def test_add_voice_not_implemented(self, client):
        """add_voice returns not implemented."""
        response = client.post(
            "/add_voice",
            json={
                "existing_voice": "C4, D4, E4",
                "new_voice_type": "bass",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False

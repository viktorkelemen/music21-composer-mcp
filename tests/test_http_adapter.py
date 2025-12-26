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


class TestNotImplementedEndpoints:
    """Tests for not-yet-implemented endpoints."""

    def test_generate_melody_not_implemented(self, client):
        """generate_melody returns not implemented."""
        response = client.post(
            "/generate_melody",
            json={
                "key": "C major",
                "length_measures": 8,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert "NOT_IMPLEMENTED" in str(data["error"])

    def test_realize_chord_not_implemented(self, client):
        """realize_chord returns not implemented."""
        response = client.post(
            "/realize_chord",
            json={"chord_symbol": "Cmaj7"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False

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

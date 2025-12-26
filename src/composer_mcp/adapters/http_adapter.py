"""FastAPI HTTP adapter for the composition service."""

from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from composer_mcp.core.models import (
    ApiResponse,
    ExportMidiRequest,
    MelodyRequest,
    TransformRequest,
    ReharmonizeRequest,
    AddVoiceRequest,
    RealizeChordRequest,
)
from composer_mcp.core.service import get_service

app = FastAPI(
    title="Music21 Composer MCP",
    description="Composition-focused API built on music21",
    version="0.1.0",
)

# CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check() -> dict:
    """Health check endpoint."""
    return {"status": "healthy", "version": "0.1.0"}


@app.post("/export_midi", response_model=ApiResponse)
async def export_midi(request: ExportMidiRequest) -> ApiResponse:
    """
    Export a musical stream to MIDI format.

    Accepts MusicXML, ABC notation, or simple note lists.
    Returns base64-encoded MIDI data.
    """
    service = get_service()
    response = service.export_midi(request)

    if not response.success:
        raise HTTPException(
            status_code=400,
            detail=response.error.model_dump() if response.error else "Unknown error",
        )

    return response


@app.post("/generate_melody", response_model=ApiResponse)
async def generate_melody(request: MelodyRequest) -> ApiResponse:
    """
    Generate a melodic line based on constraints.

    Not yet implemented - returns placeholder response.
    """
    return ApiResponse(
        success=False,
        error={
            "code": "NOT_IMPLEMENTED",
            "message": "generate_melody is not yet implemented. Coming in Phase 2.",
        },
    )


@app.post("/transform_phrase", response_model=ApiResponse)
async def transform_phrase(request: TransformRequest) -> ApiResponse:
    """
    Apply musical transformations to a phrase.

    Not yet implemented - returns placeholder response.
    """
    return ApiResponse(
        success=False,
        error={
            "code": "NOT_IMPLEMENTED",
            "message": "transform_phrase is not yet implemented. Coming in Phase 5.",
        },
    )


@app.post("/reharmonize", response_model=ApiResponse)
async def reharmonize(request: ReharmonizeRequest) -> ApiResponse:
    """
    Generate alternative chord progressions for a melody.

    Not yet implemented - returns placeholder response.
    """
    return ApiResponse(
        success=False,
        error={
            "code": "NOT_IMPLEMENTED",
            "message": "reharmonize is not yet implemented. Coming in Phase 3.",
        },
    )


@app.post("/add_voice", response_model=ApiResponse)
async def add_voice(request: AddVoiceRequest) -> ApiResponse:
    """
    Generate a countermelody or additional voice part.

    Not yet implemented - returns placeholder response.
    """
    return ApiResponse(
        success=False,
        error={
            "code": "NOT_IMPLEMENTED",
            "message": "add_voice is not yet implemented. Coming in Phase 4.",
        },
    )


@app.post("/realize_chord", response_model=ApiResponse)
async def realize_chord(request: RealizeChordRequest) -> ApiResponse:
    """
    Generate specific voicings for chord symbols.

    Not yet implemented - returns placeholder response.
    """
    return ApiResponse(
        success=False,
        error={
            "code": "NOT_IMPLEMENTED",
            "message": "realize_chord is not yet implemented. Coming in Phase 2.",
        },
    )


def create_app() -> FastAPI:
    """Create and return the FastAPI app."""
    return app

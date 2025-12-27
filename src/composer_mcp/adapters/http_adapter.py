"""FastAPI HTTP adapter for the composition service."""

from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from composer_mcp.core.models import (
    ApiResponse,
    ErrorDetail,
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
    allow_credentials=False,  # Disabled with wildcard origins for security
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

    Supports key signatures, contour shapes, rhythmic density,
    range constraints, and more.
    """
    service = get_service()
    response = service.generate_melody(request)

    if not response.success:
        raise HTTPException(
            status_code=400,
            detail=response.error.model_dump() if response.error else "Unknown error",
        )

    return response


@app.post("/transform_phrase", response_model=ApiResponse)
async def transform_phrase(request: TransformRequest) -> ApiResponse:
    """
    Apply musical transformations to a phrase.

    Not yet implemented - returns placeholder response.
    """
    return ApiResponse(
        success=False,
        error=ErrorDetail(
            code="NOT_IMPLEMENTED",
            message="transform_phrase is not yet implemented. Coming in Phase 5.",
        ),
    )


@app.post("/reharmonize", response_model=ApiResponse)
async def reharmonize(request: ReharmonizeRequest) -> ApiResponse:
    """
    Generate alternative chord progressions for a melody.

    Supports 4 harmonization styles (classical, jazz, pop, modal),
    configurable chord rhythm, and bass motion preferences.
    Returns ranked options with voice leading scores.
    """
    service = get_service()
    response = service.reharmonize(request)

    if not response.success:
        raise HTTPException(
            status_code=400,
            detail=response.error.model_dump() if response.error else "Unknown error",
        )

    return response


@app.post("/add_voice", response_model=ApiResponse)
async def add_voice(request: AddVoiceRequest) -> ApiResponse:
    """
    Generate a countermelody or additional voice part.

    Not yet implemented - returns placeholder response.
    """
    return ApiResponse(
        success=False,
        error=ErrorDetail(
            code="NOT_IMPLEMENTED",
            message="add_voice is not yet implemented. Coming in Phase 4.",
        ),
    )


@app.post("/realize_chord", response_model=ApiResponse)
async def realize_chord(request: RealizeChordRequest) -> ApiResponse:
    """
    Generate specific voicings for chord symbols.

    Supports multiple voicing styles (close, open, drop2, drop3, quartal),
    inversions, instrument-specific constraints, and slash chords.
    """
    service = get_service()
    response = service.realize_chord(request)

    if not response.success:
        raise HTTPException(
            status_code=400,
            detail=response.error.model_dump() if response.error else "Unknown error",
        )

    return response


def create_app() -> FastAPI:
    """Create and return the FastAPI app."""
    return app

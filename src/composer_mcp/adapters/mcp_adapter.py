"""MCP (Model Context Protocol) adapter for the composition service."""

from __future__ import annotations

import json
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from composer_mcp.core.service import get_service
from composer_mcp.core.models import (
    ExportMidiRequest,
    MelodyRequest,
    RealizeChordRequest,
    ReharmonizeRequest,
    TransformRequest,
    AddVoiceRequest,
)

# Create the MCP server
server = Server("music21-composer")


# === Tool Definitions ===

TOOLS = [
    Tool(
        name="generate_melody",
        description="""Generate a melodic line based on musical constraints.

Supports key signatures (major, minor, modes), contour shapes (arch, ascending,
descending, wave, static), rhythmic density, range constraints, and reproducible
seeds. Returns MusicXML and note data.""",
        inputSchema={
            "type": "object",
            "properties": {
                "key": {
                    "type": "string",
                    "description": "Key signature, e.g., 'C major', 'D dorian', 'F# minor'",
                },
                "length_measures": {
                    "type": "integer",
                    "description": "Number of measures to generate (1-64)",
                    "minimum": 1,
                    "maximum": 64,
                },
                "time_signature": {
                    "type": "string",
                    "description": "Time signature, e.g., '4/4', '3/4', '6/8'",
                    "default": "4/4",
                },
                "range_low": {
                    "type": "string",
                    "description": "Lowest allowed note, e.g., 'C4'",
                    "default": "C4",
                },
                "range_high": {
                    "type": "string",
                    "description": "Highest allowed note, e.g., 'C6'",
                    "default": "C6",
                },
                "contour": {
                    "type": "string",
                    "enum": ["arch", "ascending", "descending", "wave", "static"],
                    "description": "Melodic shape/contour",
                },
                "rhythmic_density": {
                    "type": "string",
                    "enum": ["sparse", "medium", "dense"],
                    "description": "Note density",
                    "default": "medium",
                },
                "start_note": {
                    "type": "string",
                    "description": "Force starting pitch, e.g., 'C4'",
                },
                "end_note": {
                    "type": "string",
                    "description": "Force ending pitch, e.g., 'G4'",
                },
                "avoid_leaps_greater_than": {
                    "type": "string",
                    "description": "Max interval, e.g., 'P5' for perfect fifth",
                },
                "prefer_stepwise": {
                    "type": "number",
                    "description": "Probability of stepwise motion (0.0-1.0)",
                    "default": 0.7,
                },
                "seed": {
                    "type": "integer",
                    "description": "Random seed for reproducibility",
                },
            },
            "required": ["key", "length_measures"],
        },
    ),
    Tool(
        name="realize_chord",
        description="""Generate specific voicings for chord symbols.

Supports multiple voicing styles (close, open, drop2, drop3, quartal),
inversions, instrument-specific constraints (piano, guitar, SATB, strings),
and slash chords. Returns note names, MIDI pitches, and MusicXML.""",
        inputSchema={
            "type": "object",
            "properties": {
                "chord_symbol": {
                    "type": "string",
                    "description": "Chord name, e.g., 'Cmaj7', 'Dm7', 'G7', 'F#dim'",
                },
                "voicing_style": {
                    "type": "string",
                    "enum": ["close", "open", "drop2", "drop3", "quartal"],
                    "description": "Voicing style",
                    "default": "close",
                },
                "instrument": {
                    "type": "string",
                    "enum": ["piano", "guitar", "satb", "strings"],
                    "description": "Target instrument (affects range and note count)",
                    "default": "piano",
                },
                "inversion": {
                    "type": "integer",
                    "description": "Inversion (0=root position, 1=first, etc.)",
                    "default": 0,
                },
                "bass_note": {
                    "type": "string",
                    "description": "Slash chord bass note, e.g., 'E3' for C/E",
                },
                "range_low": {
                    "type": "string",
                    "description": "Lowest allowed note",
                },
                "range_high": {
                    "type": "string",
                    "description": "Highest allowed note",
                },
            },
            "required": ["chord_symbol"],
        },
    ),
    Tool(
        name="reharmonize",
        description="""Generate alternative chord progressions for a melody.

Supports 4 harmonization styles (classical, jazz, pop, modal), configurable
chord rhythm, bass motion preferences, and returns multiple ranked options
with voice leading scores.""",
        inputSchema={
            "type": "object",
            "properties": {
                "melody": {
                    "type": "string",
                    "description": "Musical input (notes like 'C4, D4, E4' or MusicXML)",
                },
                "style": {
                    "type": "string",
                    "enum": ["classical", "jazz", "pop", "modal"],
                    "description": "Harmonization style",
                },
                "chord_rhythm": {
                    "type": "string",
                    "enum": ["per_measure", "per_beat", "per_half"],
                    "description": "How often chords change",
                    "default": "per_measure",
                },
                "num_options": {
                    "type": "integer",
                    "description": "Number of harmonization options to return",
                    "default": 3,
                },
                "bass_motion": {
                    "type": "string",
                    "enum": ["stepwise", "fifths", "pedal", "any"],
                    "description": "Preferred bass motion",
                    "default": "any",
                },
            },
            "required": ["melody", "style"],
        },
    ),
    Tool(
        name="export_midi",
        description="""Export a musical stream to MIDI format.

Accepts note lists (e.g., 'C4, D4, E4'), MusicXML, or ABC notation.
Returns base64-encoded MIDI data with metadata. Supports humanization
for more natural playback.""",
        inputSchema={
            "type": "object",
            "properties": {
                "stream": {
                    "type": "string",
                    "description": "Musical input (notes, MusicXML, or ABC)",
                },
                "tempo": {
                    "type": "integer",
                    "description": "Tempo in BPM",
                    "default": 120,
                },
                "humanize": {
                    "type": "boolean",
                    "description": "Add timing/velocity variation for natural feel",
                    "default": False,
                },
                "humanize_amount": {
                    "type": "number",
                    "description": "Humanization intensity (0.0-1.0)",
                    "default": 0.3,
                },
                "velocity_curve": {
                    "type": "string",
                    "enum": ["flat", "dynamic", "crescendo", "diminuendo"],
                    "description": "Velocity curve shape",
                    "default": "flat",
                },
                "include_abc": {
                    "type": "boolean",
                    "description": "Include ABC notation in response",
                    "default": False,
                },
            },
            "required": ["stream"],
        },
    ),
]


@server.list_tools()
async def list_tools() -> list[Tool]:
    """List available composition tools."""
    return TOOLS


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Execute a composition tool."""
    service = get_service()

    try:
        if name == "generate_melody":
            request = MelodyRequest(**arguments)
            response = service.generate_melody(request)

        elif name == "realize_chord":
            request = RealizeChordRequest(**arguments)
            response = service.realize_chord(request)

        elif name == "reharmonize":
            request = ReharmonizeRequest(**arguments)
            response = service.reharmonize(request)

        elif name == "export_midi":
            request = ExportMidiRequest(**arguments)
            response = service.export_midi(request)

        elif name == "transform_phrase":
            # Not yet implemented
            return [TextContent(
                type="text",
                text=json.dumps({
                    "success": False,
                    "error": {"code": "NOT_IMPLEMENTED", "message": "transform_phrase coming in Phase 5"}
                })
            )]

        elif name == "add_voice":
            # Not yet implemented
            return [TextContent(
                type="text",
                text=json.dumps({
                    "success": False,
                    "error": {"code": "NOT_IMPLEMENTED", "message": "add_voice coming in Phase 4"}
                })
            )]

        else:
            return [TextContent(
                type="text",
                text=json.dumps({
                    "success": False,
                    "error": {"code": "UNKNOWN_TOOL", "message": f"Unknown tool: {name}"}
                })
            )]

        # Return the response as JSON
        return [TextContent(
            type="text",
            text=json.dumps(response.model_dump(), indent=2)
        )]

    except Exception as e:
        return [TextContent(
            type="text",
            text=json.dumps({
                "success": False,
                "error": {"code": "INTERNAL_ERROR", "message": str(e)}
            })
        )]


async def main():
    """Run the MCP server."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options()
        )


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())

# Music21 Composer MCP

A composition-focused MCP server built on music21, designed for **generative** workflows.

## Features

- **generate_melody** - Constraint-based melody generation
- **transform_phrase** - Musical transformations (sequence, inversion, retrograde, etc.)
- **reharmonize** - Generate alternative chord progressions
- **add_voice** - Counterpoint and voice generation
- **realize_chord** - Chord symbol to voicing
- **export_midi** - Export to MIDI format

## Installation

```bash
# Clone the repository
git clone <repo-url>
cd music21-composer-mcp

# Install with dev dependencies
pip install -e ".[dev]"
```

## Quick Start

### Start the HTTP server

```bash
composer-mcp --mode http --port 8000
```

### API Usage

```bash
# Export notes to MIDI
curl -X POST http://localhost:8000/export_midi \
  -H "Content-Type: application/json" \
  -d '{"stream": "C4, D4, E4, G4", "tempo": 120}'
```

### API Documentation

With the server running, visit http://localhost:8000/docs for interactive API documentation.

## Input Formats

The API accepts three input formats:

### 1. Note List (simplest)
```
C4, D4, E4, G4           # Quarter notes (default)
C4:h, D4:q, E4:e         # With durations (h=half, q=quarter, e=eighth)
C#4:qd, Bb3:h            # Accidentals and dotted notes
```

### 2. ABC Notation
```
X:1
M:4/4
K:C
CDEF|GABc|
```

### 3. MusicXML
Standard MusicXML format.

## Development

```bash
# Run tests
pytest

# Run with coverage
pytest --cov=composer_mcp

# Format code
black src tests
ruff check src tests
```

## Implementation Status

| Tool | Status |
|------|--------|
| `export_midi` | Implemented |
| `realize_chord` | Phase 2 |
| `generate_melody` | Phase 2 |
| `reharmonize` | Phase 3 |
| `add_voice` | Phase 4 |
| `transform_phrase` | Phase 5 |
| MCP adapter | Phase 6 |

## License

MIT

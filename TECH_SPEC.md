# Music21 Composer MCP - Technical Specification

> **Version**: 0.1.0-draft
> **Last Updated**: 2025-12-25
> **Status**: Ready for implementation

## Overview

A composition-focused MCP server built on music21, designed for **generative** workflows rather than analysis. While the existing `music21-mcp-server` excels at analysis (key detection, harmony analysis, voice leading checks), this MCP focuses on **creating** music with AI assistance.

### Goals

1. Enable Claude to generate musical content with theoretical correctness
2. Provide constraint-based composition tools
3. Support iterative composition workflows (generate → refine → generate)
4. Export results in usable formats (MIDI, MusicXML)

### Non-Goals

- Real-time audio synthesis (out of scope)
- DAW integration (future consideration)
- Full analysis suite (use existing MCP for that)
- ML-based style inference (v1 uses explicit transformations only)

---

## Architecture

### Design Principles

1. **Stateless**: No server-side session storage. Claude holds intermediate results and passes them between calls. Simpler, more reliable, easier to test.

2. **Multi-interface**: MCP has ~40-50% reliability in production. HTTP fallback ensures tools remain accessible during development and when MCP fails.

3. **Fail gracefully**: Return best-effort results with warnings rather than hard failures when possible.

```
┌─────────────────────────────────────────────────────────┐
│                    Unified Launcher                      │
├─────────────────────────────────────────────────────────┤
│   MCP Adapter   │   HTTP Adapter   │   CLI Adapter      │
├─────────────────────────────────────────────────────────┤
│              Core Composition Service                    │
│         (Protocol-independent music21 logic)            │
├─────────────────────────────────────────────────────────┤
│                     music21 Library                      │
└─────────────────────────────────────────────────────────┘
```

### Performance Considerations

**music21 Cold Start**: music21 loads corpus data on first import (~2-3 seconds). Mitigations:
- Launcher pre-imports music21 on startup
- HTTP/MCP servers keep process warm
- Document expected cold start in README

**Response Time SLAs**:
| Operation | Input Size | Target |
|-----------|-----------|--------|
| `realize_chord` | Single chord | <100ms |
| `generate_melody` | 8 measures | <500ms |
| `generate_melody` | 32 measures | <2s |
| `reharmonize` | 16 measures | <1s |
| `add_voice` | 16 measures | <1s |
| `export_midi` | Any | <200ms |

### Project Structure

```
music21-composer-mcp/
├── src/
│   └── composer_mcp/
│       ├── __init__.py
│       ├── core/
│       │   ├── __init__.py
│       │   ├── service.py          # Main composition service
│       │   ├── melody.py           # Melody generation logic
│       │   ├── harmony.py          # Reharmonization, chord voicing
│       │   ├── counterpoint.py     # Voice generation
│       │   ├── transforms.py       # Phrase transformation operations
│       │   ├── validation.py       # Input validation, constraint checking
│       │   ├── scoring.py          # Voice leading scoring algorithms
│       │   └── models.py           # Pydantic data models
│       ├── adapters/
│       │   ├── __init__.py
│       │   ├── mcp_adapter.py      # FastMCP server
│       │   ├── http_adapter.py     # FastAPI REST API
│       │   └── cli_adapter.py      # Interactive CLI
│       ├── errors.py               # Error types and codes
│       └── launcher.py             # Unified entry point
├── tests/
│   ├── test_melody.py
│   ├── test_harmony.py
│   ├── test_counterpoint.py
│   ├── test_validation.py
│   └── test_integration.py
├── examples/
│   └── composition_workflows.py
├── pyproject.toml
├── README.md
└── TECH_SPEC.md
```

---

## Error Model

All tools return responses conforming to this schema:

### Success Response

```json
{
  "success": true,
  "data": { ... },
  "warnings": []
}
```

### Failure Response

```json
{
  "success": false,
  "error": {
    "code": "INVALID_KEY",
    "message": "Unknown key signature: 'H major'. Valid examples: 'C major', 'D minor', 'F# dorian'",
    "field": "key",
    "suggestions": ["C major", "B major", "A major"]
  },
  "partial_result": null
}
```

### Partial Success Response

When generation partially succeeds (e.g., 6 of 8 requested measures generated before constraint violation):

```json
{
  "success": true,
  "data": { ... },
  "warnings": [
    {
      "code": "CONSTRAINT_RELAXED",
      "message": "Could not maintain stepwise motion in measure 7; used P4 leap",
      "measure": 7
    }
  ]
}
```

### Error Codes

| Code | Description | Applicable Tools |
|------|-------------|------------------|
| `INVALID_KEY` | Unrecognized key signature | All |
| `INVALID_NOTE` | Malformed note name (e.g., "X4") | All |
| `INVALID_RANGE` | Low > high, or impossible range | generate_melody, add_voice |
| `INVALID_INTERVAL` | Malformed interval (e.g., "X5") | generate_melody |
| `INVALID_CHORD_SYMBOL` | Unparseable chord | realize_chord, reharmonize |
| `INVALID_TIME_SIGNATURE` | Malformed time sig | generate_melody |
| `PARSE_ERROR` | Could not parse input stream | continue_phrase, reharmonize, add_voice |
| `UNSATISFIABLE_CONSTRAINTS` | Constraints cannot be met | generate_melody |
| `GENERATION_FAILED` | Max attempts exceeded | All generative tools |
| `EMPTY_INPUT` | Required input is empty | continue_phrase, reharmonize, add_voice |

---

## Input Format Detection

For tools accepting musical input (`continue_phrase`, `reharmonize`, `add_voice`, `export_midi`):

### Detection Heuristics

```python
def detect_format(input_string: str) -> str:
    stripped = input_string.strip()

    # MusicXML: starts with XML declaration or root element
    if stripped.startswith('<?xml') or stripped.startswith('<score'):
        return 'musicxml'

    # ABC: starts with field (X:, T:, M:, K:, etc.)
    if re.match(r'^[A-Z]:', stripped):
        return 'abc'

    # Note list: comma or space separated pitch names
    # e.g., "C4, D4, E4" or "C4 D4 E4"
    if re.match(r'^[A-Ga-g][#b]?\d', stripped):
        return 'notes'

    raise ParseError("Could not detect input format. Please specify format explicitly.")
```

### Explicit Format Parameter

All input-accepting tools have an optional `input_format` parameter:
- `"musicxml"` — Full MusicXML document
- `"abc"` — ABC notation
- `"notes"` — Simplified format: `"C4:q, D4:q, E4:h"` (pitch:duration)

When `input_format` is provided, auto-detection is skipped.

### Note List Format Specification

```
note     := pitch duration?
pitch    := [A-G] accidental? octave
accidental := '#' | 'b' | '##' | 'bb'
octave   := [0-9]
duration := ':' ('w' | 'h' | 'q' | 'e' | 's' | 'd'*)
            # whole, half, quarter, eighth, sixteenth
            # 'd' suffix = dotted (can stack: 'qd' = dotted quarter)

Examples:
  "C4:q, D4:q, E4:h"           # quarter, quarter, half
  "C#5:e D5:e E5:q"            # eighth, eighth, quarter (space-separated ok)
  "Bb3:qd A3:e G3:q"           # dotted quarter, eighth, quarter
  "C4 D4 E4 G4"                # no durations = all quarter notes (default)
```

---

## Tool Specifications

### 1. `generate_melody`

Generate a melodic line based on musical constraints.

#### Parameters

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| `key` | string | yes | — | Key signature (e.g., "C major", "D dorian") |
| `length_measures` | int | yes | — | Number of measures (1-64) |
| `time_signature` | string | no | "4/4" | Time signature |
| `range_low` | string | no | "C4" | Lowest allowed note |
| `range_high` | string | no | "C6" | Highest allowed note |
| `contour` | string | no | null | "arch", "ascending", "descending", "wave", "static" |
| `rhythmic_density` | string | no | "medium" | "sparse", "medium", "dense" |
| `start_note` | string | no | null | Force starting pitch |
| `end_note` | string | no | null | Force ending pitch |
| `avoid_leaps_greater_than` | string | no | null | Max interval (e.g., "P5") |
| `prefer_stepwise` | float | no | 0.7 | Probability of stepwise motion (0.0-1.0) |
| `seed` | int | no | null | Random seed for reproducibility |
| `max_attempts` | int | no | 100 | Max generation attempts before failure |

#### Algorithm: Constrained Weighted Random Walk

```python
def generate_melody(params: MelodyRequest) -> MelodyResponse:
    scale = music21.scale.ConcreteScale(params.key)
    scale_pitches = get_pitches_in_range(scale, params.range_low, params.range_high)

    if len(scale_pitches) < 3:
        raise UnsatisfiableConstraints("Range too narrow for scale")

    rng = random.Random(params.seed)
    rhythm_pattern = generate_rhythm(params.rhythmic_density, params.time_signature,
                                     params.length_measures, rng)

    for attempt in range(params.max_attempts):
        melody = []
        current_pitch = select_start_pitch(params, scale_pitches, rng)

        for i, duration in enumerate(rhythm_pattern):
            melody.append((current_pitch, duration))

            if i < len(rhythm_pattern) - 1:
                current_pitch = select_next_pitch(
                    current=current_pitch,
                    scale_pitches=scale_pitches,
                    position_ratio=i / len(rhythm_pattern),  # for contour
                    contour=params.contour,
                    prefer_stepwise=params.prefer_stepwise,
                    max_leap=params.avoid_leaps_greater_than,
                    rng=rng
                )

        # Validate end note constraint
        if params.end_note and melody[-1][0] != params.end_note:
            # Try to approach end note in final measures
            melody = adjust_ending(melody, params.end_note, scale_pitches)

        if validate_melody(melody, params):
            return build_response(melody, params)

    # Max attempts exceeded - return best effort with warning
    return build_response(best_melody, params, warnings=[...])
```

#### Contour Implementation

| Contour | Behavior |
|---------|----------|
| `arch` | Ascend to ~60% point, descend to end |
| `ascending` | Bias toward upward motion (+0.3 to up probability) |
| `descending` | Bias toward downward motion (+0.3 to down probability) |
| `wave` | Alternate direction every ~2 measures |
| `static` | Strong bias toward repeated notes and small motion |
| `null` | No contour bias, pure weighted random |

#### Rhythmic Density

| Density | Typical Note Values | Notes per Measure (4/4) |
|---------|--------------------|-----------------------|
| `sparse` | Half, dotted half, whole | 1-2 |
| `medium` | Quarter, half, dotted quarter | 2-4 |
| `dense` | Eighth, quarter, dotted eighth | 4-8 |

#### Response

```json
{
  "success": true,
  "data": {
    "melody": {
      "musicxml": "<xml>...</xml>",
      "notes": [
        {"pitch": "C4", "duration": "quarter", "measure": 1, "beat": 1},
        {"pitch": "D4", "duration": "quarter", "measure": 1, "beat": 2}
      ]
    },
    "metadata": {
      "measures": 8,
      "note_count": 24,
      "actual_range": "C4-G5",
      "key": "C major",
      "seed_used": 12345
    }
  },
  "warnings": []
}
```

---

### 2. `transform_phrase`

> **Renamed from `continue_phrase`** — scoped down to explicit transformations rather than AI-style inference.

Apply musical transformations to extend or develop a phrase.

#### Parameters

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| `input_stream` | string | yes | — | Musical input (MusicXML, ABC, or notes) |
| `input_format` | string | no | auto | "musicxml", "abc", "notes" |
| `transformation` | string | yes | — | Transformation type (see below) |
| `repetitions` | int | no | 1 | How many times to apply transformation |
| `interval` | string | no | "M2" | For sequence: transposition interval |
| `direction` | string | no | "up" | "up" or "down" for sequence/inversion |
| `append` | bool | no | true | Append to original or return only transformed |

#### Supported Transformations

| Transformation | Description | Parameters Used |
|----------------|-------------|-----------------|
| `repeat` | Exact repetition | `repetitions` |
| `sequence` | Transpose and repeat | `repetitions`, `interval`, `direction` |
| `inversion` | Flip intervals around axis | `direction` (axis = first note) |
| `retrograde` | Reverse note order | — |
| `retrograde_inversion` | Reverse + invert | `direction` |
| `augmentation` | Double durations | — |
| `diminution` | Halve durations | — |
| `fragment_first` | Use first N notes | `repetitions` (as note count) |
| `fragment_last` | Use last N notes | `repetitions` (as note count) |

#### Algorithm

```python
def transform_phrase(params: TransformRequest) -> TransformResponse:
    stream = parse_input(params.input_stream, params.input_format)

    match params.transformation:
        case "repeat":
            result = stream * params.repetitions

        case "sequence":
            interval = music21.interval.Interval(params.interval)
            if params.direction == "down":
                interval = interval.reverse()

            result = stream.copy()
            current = stream.copy()
            for _ in range(params.repetitions):
                current = current.transpose(interval)
                result.append(current)

        case "inversion":
            axis = stream.notes[0].pitch
            result = stream.invertDiatonic(axis)

        case "retrograde":
            result = stream.retrograde()

        # ... etc

    if params.append:
        final = stream.copy()
        final.append(result)
    else:
        final = result

    return build_response(final, original=stream)
```

#### Response

```json
{
  "success": true,
  "data": {
    "original": {
      "musicxml": "...",
      "notes": [...]
    },
    "transformed": {
      "musicxml": "...",
      "notes": [...]
    },
    "combined": {
      "musicxml": "...",
      "notes": [...]
    },
    "transformation_applied": "sequence",
    "parameters": {
      "interval": "M2",
      "direction": "up",
      "repetitions": 2
    }
  },
  "warnings": []
}
```

---

### 3. `reharmonize`

Generate alternative chord progressions for a given melody.

#### Parameters

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| `melody` | string | yes | — | Musical input |
| `input_format` | string | no | auto | Input format |
| `style` | string | yes | — | "classical", "jazz", "pop", "modal" |
| `chord_rhythm` | string | no | "per_measure" | "per_measure", "per_beat", "per_half" |
| `num_options` | int | no | 3 | Number of harmonization options to return |
| `allow_extended` | bool | no | varies | Allow 7ths, 9ths, etc. (default: true for jazz) |
| `bass_motion` | string | no | "any" | "stepwise", "fifths", "pedal", "any" |

#### Style Rules

**Classical:**
```python
CLASSICAL_RULES = {
    "allowed_chords": ["I", "ii", "iii", "IV", "V", "vi", "viio"],
    "prefer_extensions": False,
    "common_progressions": [
        ["I", "IV", "V", "I"],
        ["I", "vi", "IV", "V"],
        ["I", "ii", "V", "I"],
    ],
    "cadence_patterns": {
        "perfect": ["V", "I"],
        "plagal": ["IV", "I"],
        "half": ["*", "V"],
        "deceptive": ["V", "vi"],
    },
    "avoid": ["parallel_fifths", "parallel_octaves"],
}
```

**Jazz:**
```python
JAZZ_RULES = {
    "allowed_chords": ["Imaj7", "ii7", "iii7", "IVmaj7", "V7", "vi7", "vii7b5"],
    "prefer_extensions": True,
    "substitutions": {
        "tritone": {"V7": "bII7"},           # G7 -> Db7
        "relative": {"I": "vi", "IV": "ii"},  # Cmaj7 -> Am7
        "diminished": {"V7": "viio7"},
    },
    "common_progressions": [
        ["ii7", "V7", "Imaj7"],
        ["iii7", "vi7", "ii7", "V7"],
        ["Imaj7", "vi7", "ii7", "V7"],
    ],
    "allow_chromatic_approach": True,
}
```

**Pop:**
```python
POP_RULES = {
    "allowed_chords": ["I", "ii", "IV", "V", "vi"],
    "prefer_extensions": False,
    "common_progressions": [
        ["I", "V", "vi", "IV"],      # "4 chords"
        ["I", "IV", "vi", "V"],
        ["vi", "IV", "I", "V"],
    ],
    "prefer_root_position": True,
}
```

**Modal:**
```python
MODAL_RULES = {
    "chord_from_mode": True,  # Build chords from modal scale
    "avoid_tritone": True,    # Preserve modal character
    "prefer_quartal": True,   # Quartal voicings
    "pedal_bass_common": True,
}
```

#### Algorithm

```python
def reharmonize(params: ReharmonizeRequest) -> ReharmonizeResponse:
    melody = parse_input(params.melody, params.input_format)
    key = melody.analyze('key')
    rules = get_style_rules(params.style)

    chord_points = get_chord_points(melody, params.chord_rhythm)
    options = []

    for _ in range(params.num_options * 3):  # Generate extra, keep best
        progression = []

        for i, point in enumerate(chord_points):
            melody_notes = get_melody_notes_at(melody, point)

            candidates = get_chord_candidates(
                melody_notes=melody_notes,
                key=key,
                rules=rules,
                previous_chord=progression[-1] if progression else None,
                is_cadence=(i >= len(chord_points) - 2)
            )

            chord = select_chord(
                candidates=candidates,
                bass_motion_pref=params.bass_motion,
                previous_chord=progression[-1] if progression else None,
            )
            progression.append(chord)

        score = score_progression(progression, melody, rules)
        options.append((progression, score))

    # Keep top N by score
    options.sort(key=lambda x: x[1], reverse=True)
    return build_response(options[:params.num_options], melody, key)
```

#### Response

```json
{
  "success": true,
  "data": {
    "detected_key": "C major",
    "harmonizations": [
      {
        "rank": 1,
        "chords": ["Cmaj7", "Am7", "Dm7", "G7"],
        "roman_numerals": ["Imaj7", "vi7", "ii7", "V7"],
        "musicxml": "...",
        "scores": {
          "voice_leading": 0.85,
          "chord_melody_fit": 0.92,
          "style_adherence": 0.88,
          "overall": 0.88
        }
      }
    ]
  },
  "warnings": []
}
```

---

### 4. `add_voice`

Generate a countermelody or additional voice part.

#### Parameters

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| `existing_voice` | string | yes | — | Musical input |
| `input_format` | string | no | auto | Input format |
| `new_voice_type` | string | yes | — | "soprano", "alto", "tenor", "bass" |
| `relationship` | string | no | "contrary" | Motion type (see below) |
| `species` | int | no | 0 | Counterpoint species 1-5, 0=free |
| `range_low` | string | no | varies | Lowest note (defaults by voice type) |
| `range_high` | string | no | varies | Highest note (defaults by voice type) |
| `harmonic_context` | string | no | null | Chord symbols to follow |
| `seed` | int | no | null | Random seed |
| `max_attempts` | int | no | 50 | Max generation attempts |

#### Voice Ranges (Defaults)

| Voice | Low | High |
|-------|-----|------|
| soprano | C4 | A5 |
| alto | F3 | D5 |
| tenor | C3 | A4 |
| bass | E2 | E4 |

#### Relationship Types

| Relationship | Behavior |
|--------------|----------|
| `contrary` | Move opposite direction when possible |
| `oblique` | Hold notes while other voice moves |
| `parallel_thirds` | Stay a 3rd below/above |
| `parallel_sixths` | Stay a 6th below/above |
| `free` | No motion constraints, only interval rules |

#### Species Counterpoint Rules

```python
SPECIES_RULES = {
    1: {  # Note against note
        "rhythm": "match",  # Same rhythm as cantus
        "consonances": ["P1", "m3", "M3", "P5", "m6", "M6", "P8"],
        "start_end": ["P1", "P5", "P8"],
        "forbidden_parallels": ["P5", "P8"],
    },
    2: {  # Two notes against one
        "rhythm": "half",  # Two notes per cantus note
        "strong_beat": ["P1", "m3", "M3", "P5", "m6", "M6", "P8"],
        "weak_beat": ["P1", "m2", "M2", "m3", "M3", "P4", "P5", "m6", "M6", "m7", "M7", "P8"],
        "passing_tones": True,
    },
    3: {  # Four notes against one
        "rhythm": "quarter",
        "first_beat": "consonant",
        "passing_tones": True,
        "neighbor_tones": True,
    },
    4: {  # Suspensions
        "syncopation": True,
        "suspension_types": ["4-3", "7-6", "9-8"],
        "preparation": "consonant",
        "resolution": "stepwise_down",
    },
    5: {  # Florid (free combination)
        "mix_species": True,
        "embellishments": True,
    },
}
```

#### Voice Leading Score Calculation

```python
def calculate_voice_leading_score(voice1: Stream, voice2: Stream) -> VoiceLeadingAnalysis:
    """
    Returns score 0.0-1.0 where 1.0 is perfect voice leading.

    Penalties:
    - Parallel perfect 5th: -0.15 each
    - Parallel perfect 8ve: -0.15 each
    - Direct/hidden 5th/8ve: -0.05 each
    - Voice crossing: -0.10 each
    - Spacing > octave (inner voices): -0.05 each
    - Leap > P5 without recovery: -0.03 each
    - Consecutive leaps same direction: -0.02 each

    Starting score: 1.0
    """
    score = 1.0
    issues = []

    intervals = get_vertical_intervals(voice1, voice2)
    motions = get_motion_types(voice1, voice2)

    for i in range(1, len(intervals)):
        prev_interval = intervals[i-1]
        curr_interval = intervals[i]
        motion = motions[i]

        # Parallel fifths/octaves
        if motion == "parallel":
            if curr_interval.simpleName in ["P5", "P8"] and prev_interval.simpleName == curr_interval.simpleName:
                score -= 0.15
                issues.append({"type": "parallel_fifth" if "5" in curr_interval.simpleName else "parallel_octave",
                               "location": i})

        # Direct fifths/octaves
        if motion == "similar" and curr_interval.simpleName in ["P5", "P8"]:
            score -= 0.05
            issues.append({"type": "direct_fifth_octave", "location": i})

        # ... additional checks

    return VoiceLeadingAnalysis(
        score=max(0.0, score),
        parallel_fifths=[i for i in issues if i["type"] == "parallel_fifth"],
        parallel_octaves=[i for i in issues if i["type"] == "parallel_octave"],
        voice_crossings=[...],
        spacing_issues=[...],
    )
```

#### Response

```json
{
  "success": true,
  "data": {
    "new_voice": {
      "musicxml": "...",
      "notes": [...]
    },
    "combined_score": {
      "musicxml": "...",
      "parts": ["soprano", "alto"]
    },
    "voice_leading_analysis": {
      "score": 0.92,
      "parallel_fifths": [],
      "parallel_octaves": [],
      "voice_crossings": [],
      "direct_intervals": [{"location": 5, "interval": "P5"}],
      "spacing_issues": []
    }
  },
  "warnings": []
}
```

---

### 5. `realize_chord`

Generate specific voicings for chord symbols.

#### Parameters

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| `chord_symbol` | string | yes | — | Chord name (e.g., "Cmaj7", "Dm7b5") |
| `voicing_style` | string | no | "close" | "close", "open", "drop2", "drop3", "quartal" |
| `instrument` | string | no | "piano" | "piano", "guitar", "satb", "strings" |
| `inversion` | int | no | 0 | 0=root, 1=first, 2=second, etc. |
| `bass_note` | string | no | null | Slash chord bass |
| `range_low` | string | no | varies | Lowest allowed note |
| `range_high` | string | no | varies | Highest allowed note |
| `previous_voicing` | list | no | null | Previous chord notes for voice leading |

#### Voicing Algorithms

**Close Position:**
```python
def close_voicing(chord: Chord, inversion: int) -> list[Pitch]:
    """Notes stacked within an octave, minimal spacing."""
    pitches = chord.pitches
    # Rotate for inversion
    pitches = pitches[inversion:] + pitches[:inversion]
    # Stack within octave from bass
    result = [pitches[0]]
    for p in pitches[1:]:
        while p.midi <= result[-1].midi:
            p = p.transpose(12)
        result.append(p)
    return result
```

**Drop 2:**
```python
def drop2_voicing(chord: Chord) -> list[Pitch]:
    """Take close voicing, drop 2nd-from-top note an octave."""
    close = close_voicing(chord, 0)
    if len(close) >= 4:
        close[-2] = close[-2].transpose(-12)
    return sorted(close, key=lambda p: p.midi)
```

**Drop 3:**
```python
def drop3_voicing(chord: Chord) -> list[Pitch]:
    """Take close voicing, drop 3rd-from-top note an octave."""
    close = close_voicing(chord, 0)
    if len(close) >= 4:
        close[-3] = close[-3].transpose(-12)
    return sorted(close, key=lambda p: p.midi)
```

**Quartal:**
```python
def quartal_voicing(chord: Chord) -> list[Pitch]:
    """Stack in 4ths instead of 3rds."""
    root = chord.root()
    return [root, root.transpose("P4"), root.transpose("m7"), root.transpose("m10")]
```

#### Instrument Constraints

| Instrument | Max Notes | Range | Spacing Rules |
|------------|-----------|-------|---------------|
| piano | 10 | A0-C8 | None |
| guitar | 6 | E2-E6 | Max stretch ~4 frets |
| satb | 4 | E2-A5 | Voice-specific ranges |
| strings | 4 | C2-E6 | Double stops considered |

#### Response

```json
{
  "success": true,
  "data": {
    "voicing": {
      "notes": ["E2", "B3", "D4", "G4", "C5"],
      "midi_pitches": [40, 59, 62, 67, 72],
      "musicxml": "..."
    },
    "analysis": {
      "chord_quality": "major_seventh",
      "voicing_style": "drop2",
      "inversion": 1,
      "intervals_from_bass": ["P5", "m7", "m10", "P13"]
    },
    "alternatives": [
      {"notes": [...], "style": "close"},
      {"notes": [...], "style": "drop3"}
    ]
  },
  "warnings": []
}
```

---

### 6. `export_midi`

Export a musical stream to MIDI format.

#### Parameters

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| `stream` | string | yes | — | Musical input |
| `input_format` | string | no | auto | Input format |
| `tempo` | int | no | 120 | BPM |
| `humanize` | bool | no | false | Add timing/velocity variation |
| `humanize_amount` | float | no | 0.3 | Intensity 0.0-1.0 |
| `velocity_curve` | string | no | "flat" | "flat", "dynamic", "crescendo", "diminuendo" |
| `include_abc` | bool | no | false | Include ABC notation in response |

#### Humanization Algorithm

```python
def humanize(stream: Stream, amount: float, rng: Random) -> Stream:
    """
    Add human-like imperfections.

    amount=0.3 (default):
    - Timing: ±15ms gaussian jitter on note starts
    - Velocity: ±8 variation (on 0-127 scale)
    - Duration: ±5% variation
    """
    timing_jitter_ms = 50 * amount  # max ±15ms at 0.3
    velocity_jitter = int(25 * amount)  # max ±8 at 0.3
    duration_jitter = 0.15 * amount  # max ±5% at 0.3

    for note in stream.recurse().notes:
        note.offset += rng.gauss(0, timing_jitter_ms / 1000)
        note.volume.velocity += rng.randint(-velocity_jitter, velocity_jitter)
        note.volume.velocity = clamp(note.volume.velocity, 1, 127)
        note.duration.quarterLength *= (1 + rng.uniform(-duration_jitter, duration_jitter))

    return stream
```

#### Response

```json
{
  "success": true,
  "data": {
    "midi": {
      "base64": "TVRoZC...",
      "duration_seconds": 32.5,
      "track_count": 2,
      "tempo": 120
    },
    "metadata": {
      "measures": 8,
      "time_signature": "4/4",
      "key_signature": "C major",
      "note_count": 48
    },
    "abc": null
  },
  "warnings": []
}
```

---

## Data Models

```python
from pydantic import BaseModel, Field, field_validator
from typing import Optional, Literal
from enum import Enum


# === Enums ===

class ContourType(str, Enum):
    ARCH = "arch"
    ASCENDING = "ascending"
    DESCENDING = "descending"
    WAVE = "wave"
    STATIC = "static"


class RhythmicDensity(str, Enum):
    SPARSE = "sparse"
    MEDIUM = "medium"
    DENSE = "dense"


class HarmonizationStyle(str, Enum):
    CLASSICAL = "classical"
    JAZZ = "jazz"
    POP = "pop"
    MODAL = "modal"


class VoicingStyle(str, Enum):
    CLOSE = "close"
    OPEN = "open"
    DROP2 = "drop2"
    DROP3 = "drop3"
    QUARTAL = "quartal"


class TransformationType(str, Enum):
    REPEAT = "repeat"
    SEQUENCE = "sequence"
    INVERSION = "inversion"
    RETROGRADE = "retrograde"
    RETROGRADE_INVERSION = "retrograde_inversion"
    AUGMENTATION = "augmentation"
    DIMINUTION = "diminution"
    FRAGMENT_FIRST = "fragment_first"
    FRAGMENT_LAST = "fragment_last"


class VoiceType(str, Enum):
    SOPRANO = "soprano"
    ALTO = "alto"
    TENOR = "tenor"
    BASS = "bass"


class MotionRelationship(str, Enum):
    CONTRARY = "contrary"
    OBLIQUE = "oblique"
    PARALLEL_THIRDS = "parallel_thirds"
    PARALLEL_SIXTHS = "parallel_sixths"
    FREE = "free"


class InputFormat(str, Enum):
    MUSICXML = "musicxml"
    ABC = "abc"
    NOTES = "notes"


# === Validators ===

NOTE_PATTERN = r'^[A-Ga-g][#b]?[0-9]$'
INTERVAL_PATTERN = r'^(P|M|m|A|d)[1-9][0-9]?$'
KEY_PATTERN = r'^[A-Ga-g][#b]?\s+(major|minor|dorian|phrygian|lydian|mixolydian|aeolian|locrian)$'


def validate_note(v: str) -> str:
    if not re.match(NOTE_PATTERN, v):
        raise ValueError(f"Invalid note: {v}. Expected format: C4, F#5, Bb3")
    return v


def validate_key(v: str) -> str:
    if not re.match(KEY_PATTERN, v, re.IGNORECASE):
        raise ValueError(f"Invalid key: {v}. Expected format: 'C major', 'F# minor', 'D dorian'")
    return v


# === Request Models ===

class MelodyRequest(BaseModel):
    key: str = Field(..., description="Key signature")
    length_measures: int = Field(..., ge=1, le=64)
    time_signature: str = Field(default="4/4")
    range_low: str = Field(default="C4")
    range_high: str = Field(default="C6")
    contour: Optional[ContourType] = None
    rhythmic_density: RhythmicDensity = RhythmicDensity.MEDIUM
    start_note: Optional[str] = None
    end_note: Optional[str] = None
    avoid_leaps_greater_than: Optional[str] = None
    prefer_stepwise: float = Field(default=0.7, ge=0.0, le=1.0)
    seed: Optional[int] = None
    max_attempts: int = Field(default=100, ge=1, le=1000)

    _validate_key = field_validator('key')(validate_key)
    _validate_range_low = field_validator('range_low')(validate_note)
    _validate_range_high = field_validator('range_high')(validate_note)
    _validate_start = field_validator('start_note')(lambda v: validate_note(v) if v else v)
    _validate_end = field_validator('end_note')(lambda v: validate_note(v) if v else v)


class TransformRequest(BaseModel):
    input_stream: str = Field(..., min_length=1)
    input_format: Optional[InputFormat] = None
    transformation: TransformationType
    repetitions: int = Field(default=1, ge=1, le=16)
    interval: str = Field(default="M2")
    direction: Literal["up", "down"] = "up"
    append: bool = True


class ReharmonizeRequest(BaseModel):
    melody: str = Field(..., min_length=1)
    input_format: Optional[InputFormat] = None
    style: HarmonizationStyle
    chord_rhythm: Literal["per_measure", "per_beat", "per_half"] = "per_measure"
    num_options: int = Field(default=3, ge=1, le=10)
    allow_extended: Optional[bool] = None  # defaults based on style
    bass_motion: Literal["stepwise", "fifths", "pedal", "any"] = "any"


class AddVoiceRequest(BaseModel):
    existing_voice: str = Field(..., min_length=1)
    input_format: Optional[InputFormat] = None
    new_voice_type: VoiceType
    relationship: MotionRelationship = MotionRelationship.CONTRARY
    species: int = Field(default=0, ge=0, le=5)
    range_low: Optional[str] = None
    range_high: Optional[str] = None
    harmonic_context: Optional[str] = None
    seed: Optional[int] = None
    max_attempts: int = Field(default=50, ge=1, le=500)


class RealizeChordRequest(BaseModel):
    chord_symbol: str = Field(..., min_length=1)
    voicing_style: VoicingStyle = VoicingStyle.CLOSE
    instrument: Literal["piano", "guitar", "satb", "strings"] = "piano"
    inversion: int = Field(default=0, ge=0, le=6)
    bass_note: Optional[str] = None
    range_low: Optional[str] = None
    range_high: Optional[str] = None
    previous_voicing: Optional[list[str]] = None


class ExportMidiRequest(BaseModel):
    stream: str = Field(..., min_length=1)
    input_format: Optional[InputFormat] = None
    tempo: int = Field(default=120, ge=20, le=300)
    humanize: bool = False
    humanize_amount: float = Field(default=0.3, ge=0.0, le=1.0)
    velocity_curve: Literal["flat", "dynamic", "crescendo", "diminuendo"] = "flat"
    include_abc: bool = False


# === Response Models ===

class Warning(BaseModel):
    code: str
    message: str
    location: Optional[int] = None


class ErrorDetail(BaseModel):
    code: str
    message: str
    field: Optional[str] = None
    suggestions: Optional[list[str]] = None


class VoiceLeadingAnalysis(BaseModel):
    score: float = Field(ge=0.0, le=1.0)
    parallel_fifths: list[dict]
    parallel_octaves: list[dict]
    voice_crossings: list[dict]
    direct_intervals: list[dict]
    spacing_issues: list[dict]


class BaseResponse(BaseModel):
    success: bool
    warnings: list[Warning] = []
    error: Optional[ErrorDetail] = None
```

---

## Dependencies

```toml
[project]
name = "music21-composer-mcp"
version = "0.1.0"
requires-python = ">=3.10"

[project.dependencies]
# Core music library
music21 = ">=9.1.0"

# Data validation
pydantic = ">=2.0.0"

# MCP protocol
mcp = ">=1.0.0"
fastmcp = ">=2.0.0"

# HTTP adapter
fastapi = ">=0.100.0"
uvicorn = ">=0.23.0"

[project.optional-dependencies]
dev = [
    "pytest>=7.0.0",
    "pytest-cov>=4.0.0",
    "pytest-asyncio>=0.21.0",
    "black>=23.0.0",
    "ruff>=0.1.0",
    "mypy>=1.0.0",
]

[project.scripts]
composer-mcp = "composer_mcp.launcher:main"
```

**Note:** `midiutil` removed — music21's built-in MIDI export is sufficient.

---

## Implementation Phases

### Phase 1: Foundation + HTTP + Export (Week 1)
- [x] Project scaffolding (pyproject.toml, structure)
- [ ] Pydantic models for all tools
- [ ] Error types and response builders
- [ ] Input format detection
- [ ] HTTP adapter with FastAPI (primary development interface)
- [ ] `export_midi` tool (validates full pipeline)
- [ ] Basic test harness

**Exit Criteria:** Can call `export_midi` via HTTP, returns valid MIDI base64.

### Phase 2: Chord + Melody Generation
- [ ] `realize_chord` (isolated, deterministic)
- [ ] `generate_melody` with all constraints
- [ ] Unit tests for:
  - All notes within range
  - All notes in key
  - Contour followed
  - Start/end notes respected

**Exit Criteria:** Can generate 8-bar melody with specific constraints, all tests pass.

### Phase 3: Harmonization
- [ ] Style rule definitions (classical, jazz, pop, modal)
- [ ] `reharmonize` with chord candidate generation
- [ ] Voice leading scoring
- [ ] Integration tests

**Exit Criteria:** Can harmonize melody in 4 styles, returns ranked options.

### Phase 4: Counterpoint
- [ ] Voice range defaults and validation
- [ ] Species counterpoint rule engine
- [ ] `add_voice` with relationship types
- [ ] Voice leading analysis in response

**Exit Criteria:** Can add valid counterpoint to melody, no parallel 5ths/8ves.

### Phase 5: Transformations
- [ ] `transform_phrase` with all 9 transformation types
- [ ] Compound transformations (sequence + inversion)
- [ ] Integration with other tools

**Exit Criteria:** All transformations work, can chain with generate → transform → export.

### Phase 6: MCP + Polish
- [ ] FastMCP adapter wrapping HTTP endpoints
- [ ] CLI adapter for manual testing
- [ ] End-to-end integration tests
- [ ] Documentation and examples
- [ ] Performance benchmarks vs SLAs

**Exit Criteria:** Full workflow works via MCP in Claude Desktop.

---

## Test Acceptance Criteria

Coverage percentage is secondary. Tests must verify:

### `generate_melody`
- [ ] All pitches within `range_low` to `range_high`
- [ ] All pitches belong to specified scale
- [ ] Measure count matches `length_measures`
- [ ] `start_note` constraint respected when provided
- [ ] `end_note` constraint respected when provided
- [ ] No intervals larger than `avoid_leaps_greater_than`
- [ ] Same seed produces same output
- [ ] Returns partial result with warnings when constraints relaxed

### `transform_phrase`
- [ ] `sequence` transposes by correct interval
- [ ] `inversion` flips intervals correctly
- [ ] `retrograde` reverses note order exactly
- [ ] `augmentation` doubles all durations
- [ ] `append=false` returns only transformed segment

### `reharmonize`
- [ ] All chord tones are consonant with melody on strong beats
- [ ] Style rules are followed (no extensions in classical, etc.)
- [ ] Returns `num_options` distinct harmonizations
- [ ] Options are ranked by voice leading score

### `add_voice`
- [ ] No parallel 5ths or 8ves (when `avoid_parallels=true`)
- [ ] New voice stays within specified range
- [ ] Species rules followed when `species > 0`
- [ ] Voice leading score is calculated correctly

### `realize_chord`
- [ ] Output notes match chord symbol pitches
- [ ] Inversion puts correct note in bass
- [ ] Voicing style algorithm applied correctly
- [ ] Instrument constraints respected

### `export_midi`
- [ ] Output is valid MIDI (parseable by music21)
- [ ] Tempo matches requested BPM
- [ ] Humanization adds measurable variation when enabled

---

## Versioning Strategy

**Semantic Versioning:** `MAJOR.MINOR.PATCH`

- **MAJOR**: Breaking API changes (parameter rename, response structure change)
- **MINOR**: New features, new optional parameters
- **PATCH**: Bug fixes, algorithm improvements

**Deprecation Policy:**
1. Deprecated parameters/fields marked with `deprecated: true` in schema
2. Deprecated items work for 2 minor versions
3. Removal announced in CHANGELOG 1 minor version before

**Version Header:**
HTTP responses include `X-API-Version: 0.1.0`
MCP responses include `api_version` in metadata

---

## Reusable from Existing MCP

From `brightlikethelight/music21-mcp-server`:

| Component | Reuse? | Notes |
|-----------|--------|-------|
| Multi-interface architecture | ✅ Yes | Proven pattern |
| FastMCP adapter pattern | ✅ Yes | Reference setup |
| HTTP/FastAPI adapter | ✅ Yes | Similar REST patterns |
| pyproject.toml structure | ✅ Yes | Build config |
| Score import/export logic | ✅ Yes | MusicXML/MIDI parsing |
| Key analysis algorithms | ✅ Yes | For reharmonize |
| Voice leading checks | ✅ Yes | Validation |
| Harmonization (Bach/jazz) | ⚠️ Reference | Different API, use as starting point |
| Counterpoint generation | ⚠️ Reference | Species rules useful |
| Analysis tools | ❌ No | Out of scope |

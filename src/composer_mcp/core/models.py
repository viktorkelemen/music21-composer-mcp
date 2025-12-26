"""Pydantic models for all tools."""

from __future__ import annotations

import re
from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator


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


# === Validation Patterns ===

NOTE_PATTERN = re.compile(r"^[A-Ga-g][#b]?[0-9]$")
INTERVAL_PATTERN = re.compile(r"^(P|M|m|A|d)[1-9][0-9]?$")
KEY_PATTERN = re.compile(
    r"^[A-Ga-g][#b]?\s+(major|minor|dorian|phrygian|lydian|mixolydian|aeolian|locrian)$",
    re.IGNORECASE,
)
TIME_SIG_PATTERN = re.compile(r"^\d+/\d+$")


def validate_note(value: str) -> str:
    """Validate note format (e.g., C4, F#5, Bb3)."""
    if not NOTE_PATTERN.match(value):
        raise ValueError(f"Invalid note: {value}. Expected format: C4, F#5, Bb3")
    return value


def validate_key(value: str) -> str:
    """Validate key signature format (e.g., C major, D dorian)."""
    if not KEY_PATTERN.match(value):
        raise ValueError(
            f"Invalid key: {value}. Expected format: 'C major', 'F# minor', 'D dorian'"
        )
    return value


def validate_interval(value: str) -> str:
    """Validate interval format (e.g., P5, M3, m7)."""
    if not INTERVAL_PATTERN.match(value):
        raise ValueError(f"Invalid interval: {value}. Expected format: P5, M3, m7")
    return value


def validate_time_signature(value: str) -> str:
    """Validate time signature format (e.g., 4/4, 3/4, 6/8)."""
    if not TIME_SIG_PATTERN.match(value):
        raise ValueError(f"Invalid time signature: {value}. Expected format: 4/4, 3/4, 6/8")
    return value


# === Request Models ===


class MelodyRequest(BaseModel):
    """Request for generate_melody tool."""

    key: str = Field(..., description="Key signature, e.g., 'C major', 'D dorian'")
    length_measures: int = Field(..., ge=1, le=64, description="Number of measures to generate")
    time_signature: str = Field(default="4/4", description="Time signature")
    range_low: str = Field(default="C4", description="Lowest allowed note")
    range_high: str = Field(default="C6", description="Highest allowed note")
    contour: Optional[ContourType] = Field(default=None, description="Melodic shape")
    rhythmic_density: RhythmicDensity = Field(
        default=RhythmicDensity.MEDIUM, description="Note density"
    )
    start_note: Optional[str] = Field(default=None, description="Force starting pitch")
    end_note: Optional[str] = Field(default=None, description="Force ending pitch")
    avoid_leaps_greater_than: Optional[str] = Field(
        default=None, description="Max interval, e.g., 'P5'"
    )
    prefer_stepwise: float = Field(
        default=0.7, ge=0.0, le=1.0, description="Probability of stepwise motion"
    )
    seed: Optional[int] = Field(default=None, description="Random seed for reproducibility")
    max_attempts: int = Field(default=100, ge=1, le=1000, description="Max generation attempts")

    @field_validator("key")
    @classmethod
    def check_key(cls, v: str) -> str:
        return validate_key(v)

    @field_validator("time_signature")
    @classmethod
    def check_time_sig(cls, v: str) -> str:
        return validate_time_signature(v)

    @field_validator("range_low", "range_high")
    @classmethod
    def check_range_notes(cls, v: str) -> str:
        return validate_note(v)

    @field_validator("start_note", "end_note")
    @classmethod
    def check_optional_notes(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            return validate_note(v)
        return v

    @field_validator("avoid_leaps_greater_than")
    @classmethod
    def check_interval(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            return validate_interval(v)
        return v


class TransformRequest(BaseModel):
    """Request for transform_phrase tool."""

    input_stream: str = Field(..., min_length=1, description="Musical input")
    input_format: Optional[InputFormat] = Field(default=None, description="Input format")
    transformation: TransformationType = Field(..., description="Transformation type")
    repetitions: int = Field(default=1, ge=1, le=16, description="Repetition count")
    interval: str = Field(default="M2", description="Transposition interval for sequence")
    direction: Literal["up", "down"] = Field(default="up", description="Direction for sequence")
    append: bool = Field(default=True, description="Append to original or return only transformed")

    @field_validator("interval")
    @classmethod
    def check_interval(cls, v: str) -> str:
        return validate_interval(v)


class ReharmonizeRequest(BaseModel):
    """Request for reharmonize tool."""

    melody: str = Field(..., min_length=1, description="Musical input")
    input_format: Optional[InputFormat] = Field(default=None, description="Input format")
    style: HarmonizationStyle = Field(..., description="Harmonization style")
    chord_rhythm: Literal["per_measure", "per_beat", "per_half"] = Field(
        default="per_measure", description="Chord change frequency"
    )
    num_options: int = Field(default=3, ge=1, le=10, description="Number of options to return")
    allow_extended: Optional[bool] = Field(
        default=None, description="Allow 7ths, 9ths (default based on style)"
    )
    bass_motion: Literal["stepwise", "fifths", "pedal", "any"] = Field(
        default="any", description="Preferred bass motion"
    )


class AddVoiceRequest(BaseModel):
    """Request for add_voice tool."""

    existing_voice: str = Field(..., min_length=1, description="Musical input")
    input_format: Optional[InputFormat] = Field(default=None, description="Input format")
    new_voice_type: VoiceType = Field(..., description="Voice type to add")
    relationship: MotionRelationship = Field(
        default=MotionRelationship.CONTRARY, description="Motion relationship"
    )
    species: int = Field(default=0, ge=0, le=5, description="Counterpoint species (0=free)")
    range_low: Optional[str] = Field(default=None, description="Override voice range low")
    range_high: Optional[str] = Field(default=None, description="Override voice range high")
    harmonic_context: Optional[str] = Field(default=None, description="Chord symbols to follow")
    seed: Optional[int] = Field(default=None, description="Random seed")
    max_attempts: int = Field(default=50, ge=1, le=500, description="Max generation attempts")

    @field_validator("range_low", "range_high")
    @classmethod
    def check_range_notes(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            return validate_note(v)
        return v


class RealizeChordRequest(BaseModel):
    """Request for realize_chord tool."""

    chord_symbol: str = Field(..., min_length=1, description="Chord name, e.g., 'Cmaj7'")
    voicing_style: VoicingStyle = Field(default=VoicingStyle.CLOSE, description="Voicing style")
    instrument: Literal["piano", "guitar", "satb", "strings"] = Field(
        default="piano", description="Target instrument"
    )
    inversion: int = Field(default=0, ge=0, le=6, description="Inversion (0=root position)")
    bass_note: Optional[str] = Field(default=None, description="Slash chord bass note")
    range_low: Optional[str] = Field(default=None, description="Lowest allowed note")
    range_high: Optional[str] = Field(default=None, description="Highest allowed note")
    previous_voicing: Optional[list[str]] = Field(
        default=None, description="Previous chord for voice leading"
    )

    @field_validator("bass_note", "range_low", "range_high")
    @classmethod
    def check_optional_notes(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            return validate_note(v)
        return v


class ExportMidiRequest(BaseModel):
    """Request for export_midi tool."""

    stream: str = Field(..., min_length=1, description="Musical input")
    input_format: Optional[InputFormat] = Field(default=None, description="Input format")
    tempo: int = Field(default=120, ge=20, le=300, description="Tempo in BPM")
    humanize: bool = Field(default=False, description="Add timing/velocity variation")
    humanize_amount: float = Field(default=0.3, ge=0.0, le=1.0, description="Humanization intensity")
    velocity_curve: Literal["flat", "dynamic", "crescendo", "diminuendo"] = Field(
        default="flat", description="Velocity curve"
    )
    include_abc: bool = Field(default=False, description="Include ABC notation in response")


# === Response Models ===


class Warning(BaseModel):
    """Warning about non-fatal issues."""

    code: str
    message: str
    location: Optional[int] = None


class ErrorDetail(BaseModel):
    """Error details for failed requests."""

    code: str
    message: str
    field: Optional[str] = None
    suggestions: Optional[list[str]] = None


class NoteData(BaseModel):
    """Single note representation."""

    pitch: str
    duration: str
    measure: Optional[int] = None
    beat: Optional[float] = None


class MelodyData(BaseModel):
    """Melody output data."""

    musicxml: str
    notes: list[NoteData]


class MelodyMetadata(BaseModel):
    """Metadata about generated melody."""

    measures: int
    note_count: int
    actual_range: str
    key: str
    seed_used: Optional[int] = None


class MelodyResponseData(BaseModel):
    """Data for melody response."""

    melody: MelodyData
    metadata: MelodyMetadata


class MidiData(BaseModel):
    """MIDI export data."""

    base64: str
    duration_seconds: float
    track_count: int
    tempo: int


class MidiMetadata(BaseModel):
    """Metadata about exported MIDI."""

    measures: int
    time_signature: str
    key_signature: Optional[str] = None
    note_count: int


class MidiResponseData(BaseModel):
    """Data for MIDI export response."""

    midi: MidiData
    metadata: MidiMetadata
    abc: Optional[str] = None


class VoiceLeadingAnalysis(BaseModel):
    """Voice leading analysis results."""

    score: float = Field(ge=0.0, le=1.0)
    parallel_fifths: list[dict] = Field(default_factory=list)
    parallel_octaves: list[dict] = Field(default_factory=list)
    voice_crossings: list[dict] = Field(default_factory=list)
    direct_intervals: list[dict] = Field(default_factory=list)
    spacing_issues: list[dict] = Field(default_factory=list)


class VoicingData(BaseModel):
    """Chord voicing data."""

    notes: list[str]
    midi_pitches: list[int]
    musicxml: str


class VoicingAnalysis(BaseModel):
    """Analysis of chord voicing."""

    chord_quality: str
    voicing_style: str
    inversion: int
    intervals_from_bass: list[str]


class ChordResponseData(BaseModel):
    """Data for chord realization response."""

    voicing: VoicingData
    analysis: VoicingAnalysis
    alternatives: list[dict] = Field(default_factory=list)


# === Generic Response Wrapper ===


class ApiResponse(BaseModel):
    """Standard API response wrapper."""

    success: bool
    data: Optional[dict] = None
    warnings: list[Warning] = Field(default_factory=list)
    error: Optional[ErrorDetail] = None
    api_version: str = "0.1.0"

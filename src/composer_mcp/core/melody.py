"""Melody generation tools."""

from __future__ import annotations

import random
from typing import TYPE_CHECKING, Optional

from music21 import duration, interval, key, note, pitch, stream

from composer_mcp.core.models import (
    ApiResponse,
    ContourType,
    MelodyData,
    MelodyMetadata,
    MelodyRequest,
    MelodyResponseData,
    NoteData,
    RhythmicDensity,
    Warning,
)
from composer_mcp.errors import (
    InvalidKeyError,
    InvalidRangeError,
    UnsatisfiableConstraintsError,
    success_response,
    partial_success_response,
)

if TYPE_CHECKING:
    from music21.pitch import Pitch


# Rhythm patterns by density
RHYTHM_PATTERNS = {
    RhythmicDensity.SPARSE: [
        [2.0, 2.0],  # half, half
        [4.0],  # whole
        [3.0, 1.0],  # dotted half, quarter
        [2.0, 1.0, 1.0],  # half, quarter, quarter
    ],
    RhythmicDensity.MEDIUM: [
        [1.0, 1.0, 1.0, 1.0],  # 4 quarters
        [1.0, 1.0, 2.0],  # quarter, quarter, half
        [2.0, 1.0, 1.0],  # half, quarter, quarter
        [1.5, 0.5, 1.0, 1.0],  # dotted quarter, eighth, quarter, quarter
        [1.0, 1.0, 1.0, 0.5, 0.5],  # quarters and eighths
    ],
    RhythmicDensity.DENSE: [
        [0.5, 0.5, 0.5, 0.5, 1.0, 1.0],  # eighths and quarters
        [0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5],  # 8 eighths
        [1.0, 0.5, 0.5, 0.5, 0.5, 1.0],  # mixed
        [0.25, 0.25, 0.5, 0.5, 0.5, 1.0, 1.0],  # sixteenths to quarters
    ],
}


def parse_key_signature(key_str: str) -> key.Key:
    """Parse key string like 'C major' or 'D dorian' into music21 Key."""
    parts = key_str.strip().split()
    if len(parts) != 2:
        raise InvalidKeyError(
            f"Invalid key format: {key_str}",
            field="key",
            suggestions=["C major", "D minor", "G dorian"],
        )

    tonic = parts[0]
    mode = parts[1].lower()

    return key.Key(tonic, mode)


def get_scale_pitches_in_range(
    k: key.Key,
    range_low: str,
    range_high: str,
) -> list["Pitch"]:
    """Get all scale pitches within the specified range."""
    low = pitch.Pitch(range_low)
    high = pitch.Pitch(range_high)

    if low.midi >= high.midi:
        raise InvalidRangeError(
            f"Range low ({range_low}) must be below range high ({range_high})",
            field="range_low",
        )

    sc = k.getScale()
    pitches = []

    # Start from low pitch, go up through scale
    current = pitch.Pitch(k.tonic.name + str(low.octave - 1))

    while current.midi <= high.midi + 12:
        for p in sc.getPitches(current, current.transpose("P8")):
            if low.midi <= p.midi <= high.midi:
                if not any(existing.midi == p.midi for existing in pitches):
                    pitches.append(p)
        current = current.transpose("P8")

    return sorted(pitches, key=lambda x: x.midi)


def generate_rhythm_pattern(
    density: RhythmicDensity,
    time_sig: str,
    num_measures: int,
    rng: random.Random,
) -> list[float]:
    """Generate a rhythm pattern for the melody."""
    parts = time_sig.split("/")
    beats_per_measure = int(parts[0])
    beat_unit = int(parts[1])

    # Quarter note = 1.0, adjust for beat unit
    quarter_per_beat = 4.0 / beat_unit
    total_quarters = beats_per_measure * quarter_per_beat * num_measures

    patterns = RHYTHM_PATTERNS[density]
    rhythm = []

    while sum(rhythm) < total_quarters:
        pattern = rng.choice(patterns)
        for dur in pattern:
            if sum(rhythm) + dur <= total_quarters:
                rhythm.append(dur)
            else:
                # Fill remaining time
                remaining = total_quarters - sum(rhythm)
                if remaining > 0:
                    rhythm.append(remaining)
                break

    return rhythm


def get_contour_bias(
    position_ratio: float,
    contour: Optional[ContourType],
) -> float:
    """
    Get directional bias based on contour type.

    Returns a value from -1.0 (strongly down) to 1.0 (strongly up).
    """
    if contour is None:
        return 0.0

    if contour == ContourType.ARCH:
        # Go up until 60%, then down
        if position_ratio < 0.6:
            return 0.5  # Upward bias
        else:
            return -0.5  # Downward bias

    elif contour == ContourType.ASCENDING:
        return 0.4  # Consistent upward bias

    elif contour == ContourType.DESCENDING:
        return -0.4  # Consistent downward bias

    elif contour == ContourType.WAVE:
        # Alternate every ~25%
        import math
        return 0.4 * math.sin(position_ratio * 4 * math.pi)

    elif contour == ContourType.STATIC:
        return 0.0  # No directional bias, prefer small motion

    return 0.0


def select_next_pitch(
    current: "Pitch",
    scale_pitches: list["Pitch"],
    position_ratio: float,
    contour: Optional[ContourType],
    prefer_stepwise: float,
    max_leap: Optional[str],
    rng: random.Random,
) -> "Pitch":
    """Select the next pitch based on constraints."""
    current_idx = None
    for i, p in enumerate(scale_pitches):
        if p.midi == current.midi:
            current_idx = i
            break

    if current_idx is None:
        # Current pitch not in scale, find nearest
        current_idx = min(
            range(len(scale_pitches)),
            key=lambda i: abs(scale_pitches[i].midi - current.midi)
        )

    # Get contour bias
    bias = get_contour_bias(position_ratio, contour)

    # Build weighted candidates
    candidates = []

    for i, p in enumerate(scale_pitches):
        step_distance = abs(i - current_idx)
        midi_distance = abs(p.midi - current.midi)

        # Check max leap constraint
        if max_leap:
            max_interval = interval.Interval(max_leap)
            if midi_distance > max_interval.semitones:
                continue

        # Base weight
        weight = 1.0

        # Prefer stepwise motion
        if step_distance <= 1:
            weight *= (1.0 + prefer_stepwise * 2)
        elif step_distance == 2:
            weight *= (1.0 + prefer_stepwise * 0.5)
        else:
            weight *= (1.0 - prefer_stepwise * 0.3)

        # Apply contour bias
        if p.midi > current.midi and bias > 0:
            weight *= (1.0 + bias)
        elif p.midi < current.midi and bias < 0:
            weight *= (1.0 - bias)
        elif p.midi == current.midi:
            if contour == ContourType.STATIC:
                weight *= 1.5
            else:
                weight *= 0.5

        if weight > 0:
            candidates.append((p, weight))

    if not candidates:
        # Fallback: return current pitch
        return current

    # Weighted random selection
    total_weight = sum(w for _, w in candidates)
    r = rng.random() * total_weight

    cumulative = 0
    for p, w in candidates:
        cumulative += w
        if r <= cumulative:
            return p

    return candidates[-1][0]


def generate_melody(request: MelodyRequest) -> ApiResponse:
    """
    Generate a melodic line based on constraints.

    Args:
        request: Melody generation parameters

    Returns:
        ApiResponse with melody data
    """
    # Parse key
    k = parse_key_signature(request.key)

    # Get scale pitches in range
    scale_pitches = get_scale_pitches_in_range(
        k, request.range_low, request.range_high
    )

    if len(scale_pitches) < 3:
        raise UnsatisfiableConstraintsError(
            f"Range {request.range_low}-{request.range_high} is too narrow for "
            f"key {request.key}. Only {len(scale_pitches)} scale tones available.",
            field="range_low",
        )

    # Initialize RNG with deterministic seed
    if request.seed is not None:
        seed_used = request.seed
    else:
        seed_used = random.randint(0, 2**31)
    rng = random.Random(seed_used)

    # Generate rhythm
    rhythm = generate_rhythm_pattern(
        request.rhythmic_density,
        request.time_signature,
        request.length_measures,
        rng,
    )

    warnings = []
    best_melody = None
    best_score = -1

    for attempt in range(request.max_attempts):
        melody_notes = []

        # Select starting pitch
        if request.start_note:
            current = pitch.Pitch(request.start_note)
            # Verify it's in range
            if not any(p.midi == current.midi for p in scale_pitches):
                # Find nearest scale pitch
                current = min(scale_pitches, key=lambda p: abs(p.midi - current.midi))
                if attempt == 0:
                    warnings.append(Warning(
                        code="START_NOTE_ADJUSTED",
                        message=f"Start note adjusted to nearest scale tone: {current.nameWithOctave}",
                    ))
        else:
            # Start on tonic or random scale tone
            tonic_pitches = [p for p in scale_pitches if p.name == k.tonic.name]
            if tonic_pitches:
                current = rng.choice(tonic_pitches)
            else:
                current = rng.choice(scale_pitches)

        # Generate melody
        for i, dur in enumerate(rhythm):
            n = note.Note(current)
            n.duration = duration.Duration(dur)
            melody_notes.append(n)

            # Select next pitch (except for last note)
            if i < len(rhythm) - 1:
                position_ratio = i / len(rhythm)
                current = select_next_pitch(
                    current=current,
                    scale_pitches=scale_pitches,
                    position_ratio=position_ratio,
                    contour=request.contour,
                    prefer_stepwise=request.prefer_stepwise,
                    max_leap=request.avoid_leaps_greater_than,
                    rng=rng,
                )

        # Handle end note constraint
        if request.end_note:
            target = pitch.Pitch(request.end_note)
            if melody_notes[-1].pitch.midi != target.midi:
                # Try to adjust last few notes to reach target
                target_in_scale = any(p.midi == target.midi for p in scale_pitches)
                if target_in_scale:
                    melody_notes[-1].pitch = target
                else:
                    nearest = min(scale_pitches, key=lambda p: abs(p.midi - target.midi))
                    melody_notes[-1].pitch = nearest
                    if attempt == 0:
                        warnings.append(Warning(
                            code="END_NOTE_ADJUSTED",
                            message=f"End note adjusted to nearest scale tone: {nearest.nameWithOctave}",
                        ))

        # Score this attempt
        score = 0

        # Check all constraints
        all_in_range = all(
            pitch.Pitch(request.range_low).midi <= n.pitch.midi <= pitch.Pitch(request.range_high).midi
            for n in melody_notes
        )
        if all_in_range:
            score += 1

        # Check leap constraints
        if request.avoid_leaps_greater_than:
            max_interval = interval.Interval(request.avoid_leaps_greater_than)
            leaps_ok = True
            for i in range(1, len(melody_notes)):
                midi_diff = abs(melody_notes[i].pitch.midi - melody_notes[i-1].pitch.midi)
                if midi_diff > max_interval.semitones:
                    leaps_ok = False
                    break
            if leaps_ok:
                score += 1

        if score > best_score:
            best_score = score
            best_melody = melody_notes

        # If perfect score, we're done
        if score == 2 or (score == 1 and not request.avoid_leaps_greater_than):
            break

    if best_melody is None:
        raise UnsatisfiableConstraintsError(
            "Could not generate melody satisfying constraints",
        )

    # Build stream
    s = stream.Stream()
    s.append(k)

    # Parse time signature
    from music21 import meter
    ts = meter.TimeSignature(request.time_signature)
    s.append(ts)

    for n in best_melody:
        s.append(n)

    # Export to MusicXML
    from composer_mcp.core.validation import stream_to_musicxml
    musicxml = stream_to_musicxml(s)

    # Build note data
    notes_data = []
    current_measure = 1
    current_beat = 1.0

    parts = request.time_signature.split("/")
    beats_per_measure = int(parts[0])

    for n in best_melody:
        notes_data.append(NoteData(
            pitch=n.pitch.nameWithOctave,
            duration=n.duration.type if hasattr(n.duration, 'type') else "quarter",
            measure=current_measure,
            beat=current_beat,
        ))

        current_beat += n.duration.quarterLength
        while current_beat > beats_per_measure:
            current_beat -= beats_per_measure
            current_measure += 1

    # Determine actual range used
    pitches_used = [n.pitch for n in best_melody]
    lowest = min(pitches_used, key=lambda p: p.midi)
    highest = max(pitches_used, key=lambda p: p.midi)
    actual_range = f"{lowest.nameWithOctave}-{highest.nameWithOctave}"

    response_data = MelodyResponseData(
        melody=MelodyData(
            musicxml=musicxml,
            notes=notes_data,
        ),
        metadata=MelodyMetadata(
            measures=request.length_measures,
            note_count=len(best_melody),
            actual_range=actual_range,
            key=request.key,
            seed_used=seed_used,
        ),
    )

    if warnings:
        return partial_success_response(response_data, warnings)

    return success_response(response_data)

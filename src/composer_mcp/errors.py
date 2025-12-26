"""Error types and response builders."""

from __future__ import annotations

from typing import Any, Optional

from composer_mcp.core.models import ApiResponse, ErrorDetail, Warning


class ComposerError(Exception):
    """Base exception for composer errors."""

    code: str = "UNKNOWN_ERROR"

    def __init__(
        self,
        message: str,
        field: Optional[str] = None,
        suggestions: Optional[list[str]] = None,
    ):
        super().__init__(message)
        self.message = message
        self.field = field
        self.suggestions = suggestions

    def to_error_detail(self) -> ErrorDetail:
        return ErrorDetail(
            code=self.code,
            message=self.message,
            field=self.field,
            suggestions=self.suggestions,
        )


class InvalidKeyError(ComposerError):
    """Raised when key signature is invalid."""

    code = "INVALID_KEY"


class InvalidNoteError(ComposerError):
    """Raised when note format is invalid."""

    code = "INVALID_NOTE"


class InvalidRangeError(ComposerError):
    """Raised when range is invalid (low > high or impossible)."""

    code = "INVALID_RANGE"


class InvalidIntervalError(ComposerError):
    """Raised when interval format is invalid."""

    code = "INVALID_INTERVAL"


class InvalidChordSymbolError(ComposerError):
    """Raised when chord symbol cannot be parsed."""

    code = "INVALID_CHORD_SYMBOL"


class InvalidTimeSignatureError(ComposerError):
    """Raised when time signature is invalid."""

    code = "INVALID_TIME_SIGNATURE"


class ParseError(ComposerError):
    """Raised when input stream cannot be parsed."""

    code = "PARSE_ERROR"


class UnsatisfiableConstraintsError(ComposerError):
    """Raised when constraints cannot be satisfied."""

    code = "UNSATISFIABLE_CONSTRAINTS"


class GenerationFailedError(ComposerError):
    """Raised when max attempts exceeded."""

    code = "GENERATION_FAILED"


class EmptyInputError(ComposerError):
    """Raised when required input is empty."""

    code = "EMPTY_INPUT"


# === Response Builders ===


def success_response(
    data: Any,
    warnings: Optional[list[Warning]] = None,
) -> ApiResponse:
    """Build a successful API response."""
    # Convert Pydantic models to dicts if needed
    if hasattr(data, "model_dump"):
        data = data.model_dump()

    return ApiResponse(
        success=True,
        data=data,
        warnings=warnings or [],
    )


def error_response(error: ComposerError | Exception) -> ApiResponse:
    """Build an error API response."""
    if isinstance(error, ComposerError):
        error_detail = error.to_error_detail()
    else:
        error_detail = ErrorDetail(
            code="INTERNAL_ERROR",
            message=str(error),
        )

    return ApiResponse(
        success=False,
        error=error_detail,
    )


def partial_success_response(
    data: Any,
    warnings: list[Warning],
) -> ApiResponse:
    """Build a partial success response with warnings."""
    if hasattr(data, "model_dump"):
        data = data.model_dump()

    return ApiResponse(
        success=True,
        data=data,
        warnings=warnings,
    )

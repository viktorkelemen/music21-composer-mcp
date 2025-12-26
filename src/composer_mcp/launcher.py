"""Unified launcher for all interfaces."""

from __future__ import annotations

import argparse
import sys


def run_http(host: str = "127.0.0.1", port: int = 8000) -> None:
    """Run the HTTP server."""
    import uvicorn
    from composer_mcp.adapters.http_adapter import app

    print(f"Starting HTTP server at http://{host}:{port}")
    print("API docs available at http://{host}:{port}/docs")
    uvicorn.run(app, host=host, port=port)


def run_mcp() -> None:
    """Run the MCP server."""
    print("MCP server not yet implemented. Coming in Phase 6.")
    print("Use HTTP mode for now: composer-mcp --mode http")
    sys.exit(1)


def run_cli() -> None:
    """Run the interactive CLI."""
    print("CLI not yet implemented. Coming in Phase 6.")
    print("Use HTTP mode for now: composer-mcp --mode http")
    sys.exit(1)


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Music21 Composer MCP - Composition-focused MCP server"
    )
    parser.add_argument(
        "--mode",
        choices=["http", "mcp", "cli"],
        default="http",
        help="Server mode (default: http)",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="HTTP host (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="HTTP port (default: 8000)",
    )

    args = parser.parse_args()

    # Pre-import music21 to warm up
    print("Warming up music21 (this may take a few seconds on first run)...")
    import music21  # noqa: F401
    print("Ready!")

    if args.mode == "http":
        run_http(args.host, args.port)
    elif args.mode == "mcp":
        run_mcp()
    elif args.mode == "cli":
        run_cli()


if __name__ == "__main__":
    main()

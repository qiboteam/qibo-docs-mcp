"""CLI entry point for qibo-docs-mcp."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .constants import DEFAULT_DB_PATH, LIBRARIES, LIBRARY_MAP


def _cmd_index(args: argparse.Namespace) -> None:
    """Force-rebuild the documentation index."""
    import httpx

    from . import store as _store
    from .fetcher import fetch_library_pages, get_latest_commit_sha

    db_path: Path = args.db
    targets = [LIBRARY_MAP[args.library]] if args.library else LIBRARIES

    with httpx.Client() as client:
        for lib in targets:
            print(f"Fetching latest commit SHA for {lib.name}...")
            try:
                sha = get_latest_commit_sha(lib.name, client)
            except Exception as exc:
                print(f"ERROR: could not fetch SHA for {lib.name}: {exc}", file=sys.stderr)
                continue

            print(f"Indexing {lib.name} @ {sha[:8]} ...")
            try:
                pages = fetch_library_pages(lib.name, client)
                _store.build_library(lib.name, pages, sha, db_path)
                print(f"  ✓ Indexed {len(pages)} pages for {lib.name}")
            except Exception as exc:
                print(f"  ✗ ERROR indexing {lib.name}: {exc}", file=sys.stderr)


def _cmd_serve(args: argparse.Namespace) -> None:
    """Start the MCP server (auto-checks for updates first)."""
    from .server import run_server

    run_server(db_path=args.db, force_reindex=args.force)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="qibo-docs-mcp",
        description="MCP server for qibo, qibolab and qibocal documentation.",
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=DEFAULT_DB_PATH,
        metavar="PATH",
        help=f"Path to the SQLite index database (default: {DEFAULT_DB_PATH})",
    )

    sub = parser.add_subparsers(dest="command", required=True)

    # index subcommand
    idx = sub.add_parser("index", help="Build or refresh the documentation index.")
    idx.add_argument(
        "--library",
        choices=list(LIBRARY_MAP),
        default=None,
        help="Index only this library (default: all three).",
    )
    idx.set_defaults(func=_cmd_index)

    # serve subcommand
    srv = sub.add_parser("serve", help="Start the MCP server (stdio transport).")
    srv.add_argument(
        "--force",
        action="store_true",
        help="Force re-index all libraries even if already up-to-date.",
    )
    srv.set_defaults(func=_cmd_serve)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()

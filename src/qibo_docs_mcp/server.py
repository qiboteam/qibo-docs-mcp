"""FastMCP server exposing qibo, qibolab and qibocal documentation."""

from __future__ import annotations

import sys
from pathlib import Path

import httpx
from fastmcp import FastMCP

from . import store as _store
from .constants import DEFAULT_DB_PATH, DEFAULT_TOP_K, LIBRARIES, LIBRARY_MAP
from .fetcher import fetch_library_pages, get_latest_commit_sha

mcp = FastMCP("qibo-docs")


# ---------------------------------------------------------------------------
# Startup: check each library for new commits and re-index if needed
# ---------------------------------------------------------------------------

def _sync_libraries(db_path: Path = DEFAULT_DB_PATH, force: bool = False) -> None:
    """For each library check the latest commit SHA and re-index if changed."""
    with httpx.Client() as client:
        for lib in LIBRARIES:
            print(f"[qibo-docs-mcp] Checking {lib.name}...", file=sys.stderr)
            try:
                latest_sha = get_latest_commit_sha(lib.name, client)
            except Exception as exc:
                print(f"[qibo-docs-mcp] WARNING: could not fetch SHA for {lib.name}: {exc}",
                      file=sys.stderr)
                continue

            if not force and not _store.needs_update(lib.name, latest_sha, db_path):
                print(f"[qibo-docs-mcp] {lib.name} is up-to-date ({latest_sha[:8]})",
                      file=sys.stderr)
                continue

            print(f"[qibo-docs-mcp] Indexing {lib.name} @ {latest_sha[:8]}...", file=sys.stderr)
            try:
                pages = fetch_library_pages(lib.name, client)
                _store.build_library(lib.name, pages, latest_sha, db_path)
                print(f"[qibo-docs-mcp] Indexed {len(pages)} pages for {lib.name}",
                      file=sys.stderr)
            except Exception as exc:
                print(f"[qibo-docs-mcp] ERROR indexing {lib.name}: {exc}", file=sys.stderr)


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

@mcp.tool()
def search_docs(
    query: str,
    library: str | None = None,
    top_k: int = DEFAULT_TOP_K,
) -> str:
    """Search qibo, qibolab and qibocal documentation using full-text BM25 search.

    Args:
        query:   Search query — keywords, phrases, API names, concepts.
        library: Optional filter — one of 'qibo', 'qibolab', 'qibocal'.
                 Omit to search all three libraries.
        top_k:   Maximum number of results to return (default 5).

    Returns:
        Markdown-formatted list of ranked results with title, snippet and source URL.
    """
    if library and library not in LIBRARY_MAP:
        return f"Unknown library '{library}'. Valid values: {', '.join(LIBRARY_MAP)}."

    try:
        results = _store.search(query, library=library, top_k=top_k)
    except Exception as exc:
        return f"Search error: {exc}"

    if not results:
        scope = f" in {library}" if library else ""
        return f"No results found for '{query}'{scope}. Try broader terms or run `qibo-docs-mcp index` to refresh."

    lines = [f"## Search results for '{query}'\n"]
    for i, r in enumerate(results, 1):
        lines.append(f"### {i}. [{r.title}]({r.source_url})")
        lines.append(f"**Library:** {r.library} · **File:** `{r.path}`\n")
        lines.append(r.snippet)
        lines.append("")
    return "\n".join(lines)


@mcp.tool()
def get_page(
    library: str,
    path: str,
    max_length: int = 20_000,
    offset: int = 0,
) -> dict:
    """Retrieve the full Markdown content of a specific documentation page.

    Args:
        library:    One of 'qibo', 'qibolab', 'qibocal'.
        path:       File path relative to doc/source/, e.g. 'getting-started/index.rst'.
                    Use list_pages to discover available paths.
        max_length: Maximum characters to return (default 20000, 0 = unlimited).
        offset:     Character offset for pagination (default 0).

    Returns:
        Dict with 'content', 'source_url', 'has_more', 'next_offset', 'total_length'.
    """
    if library not in LIBRARY_MAP:
        return {"error": f"Unknown library '{library}'. Valid values: {', '.join(LIBRARY_MAP)}."}

    markdown = _store.fetch_page(library, path)
    if markdown is None:
        return {"error": f"Page not found: {library}/{path}. Use list_pages to see available paths."}

    total = len(markdown)
    chunk = markdown[offset:] if max_length == 0 else markdown[offset: offset + max_length]
    next_offset = offset + len(chunk)
    has_more = next_offset < total

    # Retrieve source URL
    pages = _store.list_pages(library)
    source_url = next((p["source_url"] for p in pages if p["path"] == path), "")

    return {
        "content": chunk,
        "source_url": source_url,
        "has_more": has_more,
        "next_offset": next_offset if has_more else None,
        "total_length": total,
    }


@mcp.tool()
def list_pages(library: str | None = None) -> str:
    """List all indexed documentation pages.

    Args:
        library: Optional filter — one of 'qibo', 'qibolab', 'qibocal'.
                 Omit to list pages from all three libraries.

    Returns:
        Markdown table of available pages with their library, path and source URL.
    """
    if library and library not in LIBRARY_MAP:
        return f"Unknown library '{library}'. Valid values: {', '.join(LIBRARY_MAP)}."

    pages = _store.list_pages(library)
    if not pages:
        return "No pages indexed yet. Run `qibo-docs-mcp index` to build the index."

    lines = ["| Library | Path | Title |", "|---------|------|-------|"]
    for p in pages:
        title = p["title"].replace("|", "\\|")[:60]
        lines.append(f"| {p['library']} | `{p['path']}` | {title} |")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Resources
# ---------------------------------------------------------------------------

@mcp.resource("qibo-docs://libraries")
def libraries_resource() -> str:
    """List of available libraries with their rendered documentation URLs."""
    lines = ["# Available libraries\n"]
    for lib in LIBRARIES:
        stored_sha = _store.get_stored_sha(lib.name)
        sha_info = f" (indexed: `{stored_sha[:8]}`)" if stored_sha else " *(not yet indexed)*"
        lines.append(f"- **{lib.name}**{sha_info} — {lib.rendered_url_base}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Server entry point
# ---------------------------------------------------------------------------

def run_server(db_path: Path = DEFAULT_DB_PATH, force_reindex: bool = False) -> None:
    """Sync libraries if needed, then start the MCP stdio server."""
    _sync_libraries(db_path=db_path, force=force_reindex)
    mcp.run(transport="stdio")

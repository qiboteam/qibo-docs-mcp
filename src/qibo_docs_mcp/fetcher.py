"""Fetch documentation source files from GitHub and convert to Markdown."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass

import html2text
import httpx
from docutils.core import publish_parts

from .constants import (
    GITHUB_API_BASE,
    GITHUB_RAW_BASE,
    LIBRARY_MAP,
    LibraryConfig,
)


@dataclass
class DocPage:
    library: str
    path: str       # relative path within doc_path, e.g. "getting-started/index.rst"
    title: str
    markdown: str
    source_url: str


def _github_headers() -> dict[str, str]:
    headers: dict[str, str] = {"Accept": "application/vnd.github+json"}
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def get_latest_commit_sha(library_name: str, client: httpx.Client) -> str:
    """Return the SHA of the latest commit that touched doc/source for a library."""
    lib = LIBRARY_MAP[library_name]
    url = f"{GITHUB_API_BASE}/repos/{lib.owner}/{lib.repo}/commits"
    resp = client.get(
        url,
        params={"sha": lib.branch, "path": lib.doc_path, "per_page": 1},
        headers=_github_headers(),
        timeout=15,
    )
    resp.raise_for_status()
    commits = resp.json()
    if not commits:
        raise ValueError(f"No commits found for {library_name} doc path")
    return commits[0]["sha"]


def _list_doc_files(lib: LibraryConfig, client: httpx.Client) -> list[str]:
    """Return relative paths (under doc_path) for all .rst and .md files."""
    url = f"{GITHUB_API_BASE}/repos/{lib.owner}/{lib.repo}/git/trees/{lib.branch}"
    resp = client.get(
        url,
        params={"recursive": "1"},
        headers=_github_headers(),
        timeout=30,
    )
    resp.raise_for_status()
    tree = resp.json().get("tree", [])
    prefix = lib.doc_path.rstrip("/") + "/"
    return [
        item["path"][len(prefix):]
        for item in tree
        if item["type"] == "blob"
        and item["path"].startswith(prefix)
        and item["path"].endswith((".rst", ".md"))
        and not item["path"].endswith(("conf.py",))
    ]


def _raw_url(lib: LibraryConfig, rel_path: str) -> str:
    return f"{GITHUB_RAW_BASE}/{lib.owner}/{lib.repo}/{lib.branch}/{lib.doc_path}/{rel_path}"


def _source_url(lib: LibraryConfig, rel_path: str) -> str:
    """Map a source file path to its rendered documentation URL."""
    # Strip extension and convert path separators to URL slashes
    stem = rel_path.rsplit(".", 1)[0]
    # index files map to the directory URL
    if stem.endswith("/index") or stem == "index":
        stem = stem[: -len("index")].rstrip("/")
    return lib.rendered_url_base + stem.lstrip("/")


def _extract_title_from_rst(rst_text: str) -> str:
    """Extract the first section title from RST source."""
    lines = rst_text.splitlines()
    for i, line in enumerate(lines):
        # RST titles are underlined (and optionally overlined) with punctuation
        if i + 1 < len(lines) and re.match(r"^[=\-~^#*+`:.\'\"_]{3,}$", lines[i + 1].strip()):
            if lines[i].strip():
                return lines[i].strip()
    return ""


def _rst_to_markdown(rst_text: str) -> str:
    """Convert RST source to Markdown via docutils HTML intermediate."""
    try:
        parts = publish_parts(
            source=rst_text,
            writer_name="html5",
            settings_overrides={
                "halt_level": 5,        # don't raise on warnings
                "report_level": 5,      # suppress stderr noise
                "math_output": "mathjax",
            },
        )
        html = parts["html_body"]
    except Exception:
        # Fallback: strip RST markup naively
        html = f"<pre>{rst_text}</pre>"

    converter = html2text.HTML2Text()
    converter.ignore_links = False
    converter.ignore_images = True
    converter.body_width = 0  # no line wrapping
    return converter.handle(html).strip()


def _md_to_markdown(md_text: str) -> str:
    """Pass-through: Markdown files need no conversion."""
    return md_text.strip()


def fetch_library_pages(library_name: str, client: httpx.Client) -> list[DocPage]:
    """Fetch all documentation pages for a library and return as DocPage objects."""
    lib = LIBRARY_MAP[library_name]
    rel_paths = _list_doc_files(lib, client)
    pages: list[DocPage] = []

    for rel_path in rel_paths:
        raw_url = _raw_url(lib, rel_path)
        try:
            resp = client.get(raw_url, headers=_github_headers(), timeout=20)
            resp.raise_for_status()
            content = resp.text
        except httpx.HTTPError:
            continue

        if rel_path.endswith(".rst"):
            title = _extract_title_from_rst(content) or rel_path
            markdown = _rst_to_markdown(content)
        else:
            # .md file — extract first heading as title
            first_line = content.lstrip().splitlines()[0] if content.strip() else ""
            title = first_line.lstrip("#").strip() or rel_path
            markdown = _md_to_markdown(content)

        pages.append(
            DocPage(
                library=library_name,
                path=rel_path,
                title=title,
                markdown=markdown,
                source_url=_source_url(lib, rel_path),
            )
        )

    return pages

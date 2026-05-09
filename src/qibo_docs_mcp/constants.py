"""Library configurations and application constants."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class LibraryConfig:
    name: str
    owner: str
    repo: str
    branch: str
    doc_path: str  # path inside the repo where RST/MD sources live
    rendered_url_base: str  # base URL of the rendered docs site


LIBRARIES: list[LibraryConfig] = [
    LibraryConfig(
        name="qibo",
        owner="qiboteam",
        repo="qibo",
        branch="master",
        doc_path="doc/source",
        rendered_url_base="https://qibo.science/qibo/stable/",
    ),
    LibraryConfig(
        name="qibolab",
        owner="qiboteam",
        repo="qibolab",
        branch="main",
        doc_path="doc/source",
        rendered_url_base="https://qibo.science/qibolab/stable/",
    ),
    LibraryConfig(
        name="qibocal",
        owner="qiboteam",
        repo="qibocal",
        branch="main",
        doc_path="doc/source",
        rendered_url_base="https://qibo.science/qibocal/stable/",
    ),
]

LIBRARY_MAP: dict[str, LibraryConfig] = {lib.name: lib for lib in LIBRARIES}

# Default path for the SQLite index database.
# Can be overridden with the QIBO_DOCS_DB env var.
DEFAULT_DB_PATH = Path(
    os.environ.get(
        "QIBO_DOCS_DB",
        Path.home() / ".local" / "share" / "qibo-docs-mcp" / "qibo_docs.db",
    )
)

# GitHub API base URL
GITHUB_API_BASE = "https://api.github.com"
GITHUB_RAW_BASE = "https://raw.githubusercontent.com"

# Number of top results returned by search_docs by default
DEFAULT_TOP_K = 5

# Snippet character length shown in search results
SNIPPET_LENGTH = 400

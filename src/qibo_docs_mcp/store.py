"""SQLite FTS5 index: build, search (BM25), fetch, and commit-SHA tracking."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

from .constants import DEFAULT_DB_PATH, SNIPPET_LENGTH
from .fetcher import DocPage


@dataclass
class SearchResult:
    library: str
    path: str
    title: str
    snippet: str
    source_url: str
    score: float  # BM25 rank (lower = better in SQLite FTS5)


_SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (
    library     TEXT PRIMARY KEY,
    commit_sha  TEXT NOT NULL,
    indexed_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS pages (
    id          INTEGER PRIMARY KEY,
    library     TEXT NOT NULL,
    path        TEXT NOT NULL,
    title       TEXT NOT NULL,
    markdown    TEXT NOT NULL,
    source_url  TEXT NOT NULL,
    UNIQUE (library, path)
);

CREATE VIRTUAL TABLE IF NOT EXISTS pages_fts USING fts5(
    title,
    markdown,
    content='pages',
    content_rowid='id',
    tokenize='porter unicode61'
);

CREATE TRIGGER IF NOT EXISTS pages_ai AFTER INSERT ON pages BEGIN
    INSERT INTO pages_fts(rowid, title, markdown) VALUES (new.id, new.title, new.markdown);
END;

CREATE TRIGGER IF NOT EXISTS pages_ad AFTER DELETE ON pages BEGIN
    INSERT INTO pages_fts(pages_fts, rowid, title, markdown)
        VALUES ('delete', old.id, old.title, old.markdown);
END;

CREATE TRIGGER IF NOT EXISTS pages_au AFTER UPDATE ON pages BEGIN
    INSERT INTO pages_fts(pages_fts, rowid, title, markdown)
        VALUES ('delete', old.id, old.title, old.markdown);
    INSERT INTO pages_fts(rowid, title, markdown) VALUES (new.id, new.title, new.markdown);
END;
"""


def _connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.executescript(_SCHEMA)
    return conn


def get_stored_sha(library: str, db_path: Path = DEFAULT_DB_PATH) -> str | None:
    """Return the stored commit SHA for a library, or None if not indexed."""
    conn = _connect(db_path)
    row = conn.execute("SELECT commit_sha FROM meta WHERE library = ?", (library,)).fetchone()
    conn.close()
    return row["commit_sha"] if row else None


def needs_update(library: str, latest_sha: str, db_path: Path = DEFAULT_DB_PATH) -> bool:
    stored = get_stored_sha(library, db_path)
    return stored != latest_sha


def build_library(
    library: str,
    pages: list[DocPage],
    commit_sha: str,
    db_path: Path = DEFAULT_DB_PATH,
) -> None:
    """Replace all indexed pages for a library and store the new commit SHA."""
    conn = _connect(db_path)
    with conn:
        # Remove old pages (triggers handle FTS cleanup)
        conn.execute("DELETE FROM pages WHERE library = ?", (library,))
        # Insert new pages
        conn.executemany(
            "INSERT INTO pages (library, path, title, markdown, source_url) VALUES (?,?,?,?,?)",
            [(p.library, p.path, p.title, p.markdown, p.source_url) for p in pages],
        )
        # Update meta
        conn.execute(
            "INSERT INTO meta (library, commit_sha) VALUES (?, ?)"
            " ON CONFLICT(library) DO UPDATE SET commit_sha=excluded.commit_sha,"
            " indexed_at=datetime('now')",
            (library, commit_sha),
        )
    conn.close()


def search(
    query: str,
    library: str | None = None,
    top_k: int = 5,
    db_path: Path = DEFAULT_DB_PATH,
) -> list[SearchResult]:
    """BM25-ranked full-text search over all indexed pages."""
    conn = _connect(db_path)

    if library:
        sql = """
            SELECT p.library, p.path, p.title, p.markdown, p.source_url,
                   bm25(pages_fts) AS score
            FROM pages_fts
            JOIN pages p ON pages_fts.rowid = p.id
            WHERE pages_fts MATCH ? AND p.library = ?
            ORDER BY score
            LIMIT ?
        """
        rows = conn.execute(sql, (query, library, top_k)).fetchall()
    else:
        sql = """
            SELECT p.library, p.path, p.title, p.markdown, p.source_url,
                   bm25(pages_fts) AS score
            FROM pages_fts
            JOIN pages p ON pages_fts.rowid = p.id
            WHERE pages_fts MATCH ?
            ORDER BY score
            LIMIT ?
        """
        rows = conn.execute(sql, (query, top_k)).fetchall()

    conn.close()

    results = []
    for row in rows:
        # Build a short snippet around the first query keyword match
        md: str = row["markdown"]
        first_word = query.split()[0].lower() if query.split() else ""
        idx = md.lower().find(first_word)
        if idx == -1:
            snippet = md[:SNIPPET_LENGTH]
        else:
            start = max(0, idx - 80)
            snippet = ("..." if start > 0 else "") + md[start : start + SNIPPET_LENGTH]

        results.append(
            SearchResult(
                library=row["library"],
                path=row["path"],
                title=row["title"],
                snippet=snippet.strip(),
                source_url=row["source_url"],
                score=row["score"],
            )
        )
    return results


def fetch_page(library: str, path: str, db_path: Path = DEFAULT_DB_PATH) -> str | None:
    """Return the full Markdown content of a specific page, or None if not found."""
    conn = _connect(db_path)
    row = conn.execute(
        "SELECT markdown FROM pages WHERE library = ? AND path = ?", (library, path)
    ).fetchone()
    conn.close()
    return row["markdown"] if row else None


def list_pages(
    library: str | None = None, db_path: Path = DEFAULT_DB_PATH
) -> list[dict[str, str]]:
    """Return a list of {library, path, title, source_url} for all indexed pages."""
    conn = _connect(db_path)
    if library:
        rows = conn.execute(
            "SELECT library, path, title, source_url FROM pages WHERE library = ? ORDER BY path",
            (library,),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT library, path, title, source_url FROM pages ORDER BY library, path"
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]

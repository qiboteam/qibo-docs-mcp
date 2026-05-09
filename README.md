# qibo-docs-mcp

MCP server for querying and retrieving documentation for **qibo**, **qibolab** and **qibocal** — the [qiboteam](https://github.com/qiboteam) quantum computing ecosystem.

## Features

- 📚 **All three libraries** — qibo, qibolab and qibocal indexed and searchable
- 🔄 **Always up-to-date** — on every `serve` startup the server checks the latest GitHub commit SHA per library and re-indexes any that changed
- 🔍 **BM25 full-text search** — SQLite FTS5 with porter stemming, zero external dependencies
- ⚡ **Fast** — offline index, sub-millisecond searches after first build
- 🔌 **stdio transport** — works as a subprocess with any MCP client (Copilot CLI, Claude Code, Cursor, Claude Desktop, VS Code)

## Prerequisites

- Python ≥ 3.10
- [uv](https://astral.sh/uv) (recommended)
- Internet access to GitHub (for fetching and updating the index)

## Installation

```bash
git clone https://github.com/qiboteam/qibo-docs-mcp.git
cd qibo-docs-mcp
uv sync
```

## Quick start

### 1. Build the index

On the first run (or to force a full refresh):

```bash
uv run qibo-docs-mcp index
```

This fetches all `.rst` and `.md` files from `doc/source/` in each of the three repos,
converts them to Markdown, and stores them in `~/.local/share/qibo-docs-mcp/qibo_docs.db`.

Index a single library:

```bash
uv run qibo-docs-mcp index --library qibo
```

### 2. Start the server

```bash
uv run qibo-docs-mcp serve
```

On startup the server automatically checks for new commits and re-indexes changed libraries
before accepting MCP connections — no manual refresh needed.

### GitHub token (recommended)

The GitHub API allows 60 unauthenticated requests/hour. A personal access token raises this
to 5000/hr, which is important for full index builds (hundreds of RST files).

```bash
export GITHUB_TOKEN=ghp_your_token_here
```

## MCP tools

| Tool | Description |
|------|-------------|
| `search_docs(query, library?, top_k?)` | BM25 search across all indexed docs. `library` filters to `qibo`, `qibolab` or `qibocal`. |
| `get_page(library, path, max_length?, offset?)` | Return full Markdown of a specific page. Supports pagination via `offset`. |
| `list_pages(library?)` | List all indexed pages with their paths and rendered URLs. |

## MCP resource

| Resource URI | Description |
|--------------|-------------|
| `qibo-docs://libraries` | Available libraries with indexed commit SHA and rendered URL. |

## Client configuration

### Copilot CLI — `~/.copilot/mcp-config.json`

> **Note:** MCP clients spawn processes without a login shell, so use the **full path** to `uv` (find it with `which uv`; if not installed, run `curl -LsSf https://astral.sh/uv/install.sh | sh`).

```json
{
  "mcpServers": {
    "qibo-docs": {
      "command": "/Users/you/.local/bin/uv",
      "args": ["run", "--directory", "/path/to/qibo-docs-mcp", "qibo-docs-mcp", "serve"],
      "env": {
        "GITHUB_TOKEN": "ghp_your_token_here"
      }
    }
  }
}
```

### Claude Desktop — `~/Library/Application Support/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "qibo-docs": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/qibo-docs-mcp", "qibo-docs-mcp", "serve"],
      "env": {
        "GITHUB_TOKEN": "ghp_your_token_here"
      }
    }
  }
}
```

### Claude Code (VS Code extension) — `.mcp.json`

```json
{
  "servers": {
    "qibo-docs": {
      "type": "stdio",
      "command": "uv",
      "args": ["run", "--directory", "/path/to/qibo-docs-mcp", "qibo-docs-mcp", "serve"],
      "env": {
        "GITHUB_TOKEN": "ghp_your_token_here"
      }
    }
  }
}
```

### Cursor — `.cursor/mcp.json`

```json
{
  "mcpServers": {
    "qibo-docs": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/qibo-docs-mcp", "qibo-docs-mcp", "serve"],
      "env": {
        "GITHUB_TOKEN": "ghp_your_token_here"
      }
    }
  }
}
```

## Custom database path

Override the default database location with the `QIBO_DOCS_DB` environment variable:

```bash
export QIBO_DOCS_DB=/custom/path/qibo_docs.db
uv run qibo-docs-mcp serve
```

Or via the `--db` flag:

```bash
uv run qibo-docs-mcp --db /custom/path/qibo_docs.db serve
```

## Architecture

```
src/qibo_docs_mcp/
├── __init__.py      # CLI entry point (index / serve subcommands)
├── server.py        # FastMCP server: tools, resources, startup sync
├── fetcher.py       # GitHub API → RST/MD → Markdown conversion
├── store.py         # SQLite FTS5: build, BM25 search, fetch, SHA tracking
└── constants.py     # Library configs (repo, branch, doc path, rendered URL)
```

**Update flow:**
1. `serve` starts → calls `_sync_libraries()`
2. For each library, fetch latest commit SHA touching `doc/source/` via GitHub API
3. Compare with stored SHA in `meta` table
4. If changed → re-fetch all RST/MD files → rebuild FTS5 index for that library
5. Serve MCP requests with the fresh index

## Sources

All documentation is sourced directly from the official GitHub repositories:

| Library | Repository | Branch | Doc path |
|---------|------------|--------|----------|
| qibo | [qiboteam/qibo](https://github.com/qiboteam/qibo) | master | `doc/source/` |
| qibolab | [qiboteam/qibolab](https://github.com/qiboteam/qibolab) | main | `doc/source/` |
| qibocal | [qiboteam/qibocal](https://github.com/qiboteam/qibocal) | main | `doc/source/` |

## License

Apache-2.0

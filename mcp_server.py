#!/usr/bin/env python3
"""
CodeSense MCP Server
--------------------
Exposes codebase-exploration tools over the Model Context Protocol so that
any MCP-compatible client (Claude Desktop, VS Code, etc.) can query this
repository interactively.

Run standalone:
    python mcp_server.py

Or via the MCP CLI:
    mcp run mcp_server.py
"""
import json
import os
import sys
from pathlib import Path

from mcp.server.fastmcp import FastMCP

mcp = FastMCP(
    "CodeSense",
    instructions=(
        "You are connected to a live codebase. "
        "Use the provided tools to retrieve files, list the repository structure, "
        "and search for relevant paths before answering questions about the code."
    ),
)

_tree = None


def _get_tree():
    """Lazily initialise the repository tree (defaults to ./root)."""
    global _tree
    if _tree is None:
        repo_path = os.environ.get("CODESENSE_REPO", "root")
        # Import here so the server can start without Streamlit installed
        from src.treeparser import Tree
        _tree = Tree(repo_path)
    return _tree


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

@mcp.tool()
def retriever(filepath: str) -> str:
    """Fetch the full source of a file in the repository.

    Args:
        filepath: Exact path as it appears in the repository tree.
    """
    return _get_tree().get(filepath)


@mcp.tool()
def list_files() -> str:
    """Return the complete repository file tree as a newline-separated list."""
    return _get_tree().repoTree.strip()


@mcp.tool()
def search_files(query: str) -> str:
    """Find files whose paths contain *query* (case-insensitive).

    Args:
        query: Substring to search for inside file paths.
    """
    tree = _get_tree()
    matches = [p for p in tree.content.keys() if query.lower() in p.lower()]
    if not matches:
        return json.dumps({"matches": [], "count": 0})
    return json.dumps({"matches": sorted(matches), "count": len(matches)}, indent=2)


@mcp.tool()
def file_stats() -> str:
    """Return summary statistics about the loaded repository."""
    tree = _get_tree()
    total = len(tree.files)
    indexed = len(tree.content)
    extensions: dict[str, int] = {}
    for p in tree.content:
        ext = Path(p).suffix or "(none)"
        extensions[ext] = extensions.get(ext, 0) + 1
    top_exts = sorted(extensions.items(), key=lambda x: -x[1])[:10]
    return json.dumps(
        {
            "total_files": total,
            "indexed_files": indexed,
            "top_extensions": dict(top_exts),
        },
        indent=2,
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    mcp.run()

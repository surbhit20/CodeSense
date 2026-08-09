import fnmatch
import os
from pathlib import Path
from collections import deque
import mimetypes
import json

try:
    from src.scanner import scan_directory as _cpp_scan
    _HAS_CPP_SCANNER = True
except Exception:
    _HAS_CPP_SCANNER = False

# Directories that are never source — build/dependency/VCS output. Skipped
# regardless of .gitignore, since repos routinely forget to list all of these.
DEFAULT_DENY_DIRS = {
    '__pycache__', '.git', '.hg', '.svn', 'node_modules', '.venv', 'venv',
    'env', '.mypy_cache', '.pytest_cache', '.ruff_cache', '.tox',
    'dist', 'build', '.next', '.nuxt', '.idea', '.vscode',
}


class Tree():
    def __init__(self, root='root', display_name=None):
        self.root = Path(root)
        # root is always the local clone path (e.g. /tmp/codesense-repo),
        # unrelated to whatever repo actually got cloned there — the graph's
        # root node needs the real repo name, not that fixed directory name.
        self.display_name = display_name or self.root.name
        self.repoTree = ""
        self._ignore_patterns = self._load_gitignore()

        self._build()
        self._getData()

    def _load_gitignore(self):
        """Best-effort .gitignore support: plain names and glob patterns,
        matched against a path's basename or its path relative to the repo
        root. No negation/anchoring semantics — good enough to keep obvious
        ignored junk (build output, caches, env files) out of both the file
        index and the graph."""
        patterns = []
        gitignore_path = self.root / '.gitignore'
        if gitignore_path.is_file():
            try:
                for line in gitignore_path.read_text(errors='ignore').splitlines():
                    line = line.strip()
                    if line and not line.startswith('#'):
                        patterns.append(line.rstrip('/'))
            except OSError:
                pass
        return patterns

    def _is_ignored(self, path: Path) -> bool:
        if any(part in DEFAULT_DENY_DIRS for part in path.parts):
            return True
        name = path.name
        try:
            rel = str(path.relative_to(self.root))
        except ValueError:
            rel = str(path)
        for pattern in self._ignore_patterns:
            if fnmatch.fnmatch(name, pattern) or fnmatch.fnmatch(rel, pattern):
                return True
        return False

    def _build(self):
        queue = deque([self.root])
        self.files = []

        while queue:
            nodePath = queue.popleft()
            for childPath in os.listdir(nodePath):
                if childPath.startswith('.'): continue
                childPath = Path(os.path.join(nodePath, childPath))
                if self._is_ignored(childPath):
                    continue
                self.repoTree += f'\n{childPath}'
                if childPath.is_dir():
                    queue.append(childPath)
                else:
                    self.files.append(childPath)

    def _getData(self):
        self.content = dict()

        # Use C++ scanner for fast file enumeration when available
        if _HAS_CPP_SCANNER:
            all_paths, _ = _cpp_scan(str(self.root))
            candidate_files = [Path(p) for p in all_paths if os.path.isfile(p)]
        else:
            candidate_files = self.files

        for file in candidate_files:
            if self._is_ignored(file):
                continue
            mime_type, _ = mimetypes.guess_type(file)
            if mime_type is None and str(file).endswith('.ipynb'):
                mime_type = 'application/json'
            try:
                if mime_type and mime_type.startswith('text') or mime_type == 'application/json':
                    with open(file, 'r') as f:
                        if mime_type == 'application/json':
                            json_content = json.load(f)
                            file_content = json.dumps(json_content, indent=4)
                        else:
                            file_content = f.read()
                        self.content[str(file)] = file_content
                else:
                    print(f'Skipping {file} {mime_type}')
            except Exception:
                pass

    
    def get(self, filepath):
        print(f"[INFO] Trying to fetch {filepath}")
        if filepath in self.content:
            return self.content[filepath]
        print(f'[ERROR] File not found. ({filepath})')
        print(self.content.keys())
        return "File Not Found. Try Again."

    def get_graph_data(self):
        """Builds the graph directly from self.content — the same filtered
        file set the chat's file-action buttons use — so the graph and the
        chat can never disagree about what the repo "contains". Directories
        that end up with no surviving file underneath them (e.g. an
        images-only assets/ folder) simply never get a node, since they're
        only ever created as an ancestor of a kept file."""
        nodes_by_id = {}
        edges = []

        root_id = str(self.root)
        nodes_by_id[root_id] = {
            "id": root_id,
            "label": self.display_name,
            "group": "dir",
            "title": root_id,
            "depth": 0,
        }

        for filepath in sorted(self.content.keys()):
            path = Path(filepath)
            try:
                rel_parts = path.relative_to(self.root).parts
            except ValueError:
                continue
            if not rel_parts:
                continue

            parent_id = root_id
            current = self.root
            for depth, part in enumerate(rel_parts[:-1], start=1):
                current = current / part
                current_id = str(current)
                if current_id not in nodes_by_id:
                    nodes_by_id[current_id] = {
                        "id": current_id,
                        "label": part,
                        "group": "dir",
                        "title": current_id,
                        "depth": depth,
                    }
                    edges.append({"from": parent_id, "to": current_id})
                parent_id = current_id

            file_id = str(path)
            if file_id not in nodes_by_id:
                nodes_by_id[file_id] = {
                    "id": file_id,
                    "label": path.name,
                    "group": "file",
                    "title": file_id,
                    "depth": len(rel_parts),
                }
                edges.append({"from": parent_id, "to": file_id})

        return {"nodes": list(nodes_by_id.values()), "edges": edges}

if __name__ == '__main__':
    tree = Tree()
    temp = 'root/folder3/code.py'
    print(tree.repoTree)
    print(tree.content)


    
    

        
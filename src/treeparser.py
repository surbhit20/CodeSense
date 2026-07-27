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

class Tree():
    def __init__(self, root='root'):
        self.root = Path(root)
        self.repoTree = ""

        self._build()
        self._getData()

    def _build(self):
        queue = deque([self.root])
        self.files = []

        while queue:
            nodePath = queue.popleft()
            for childPath in os.listdir(nodePath):
                if childPath.startswith('.'): continue
                childPath = Path(os.path.join(nodePath, childPath))
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
        nodes, edges, visited = [], [], set()
        queue = deque([self.root])
        while queue:
            nodePath = queue.popleft()
            node_id = str(nodePath)
            if node_id not in visited:
                visited.add(node_id)
                nodes.append({
                    "id": node_id,
                    "label": nodePath.name,
                    "group": "dir" if nodePath.is_dir() else "file",
                    "title": node_id,
                })
            if nodePath.is_dir():
                try:
                    children = sorted(os.listdir(nodePath))
                except PermissionError:
                    continue
                for child in children:
                    if child.startswith('.'): continue
                    childPath = Path(os.path.join(nodePath, child))
                    child_id = str(childPath)
                    edges.append({"from": node_id, "to": child_id})
                    if child_id not in visited:
                        visited.add(child_id)
                        nodes.append({
                            "id": child_id,
                            "label": childPath.name,
                            "group": "dir" if childPath.is_dir() else "file",
                            "title": child_id,
                        })
                        if childPath.is_dir():
                            queue.append(childPath)
        return {"nodes": nodes, "edges": edges}

if __name__ == '__main__':
    tree = Tree()
    temp = 'root/folder3/code.py'
    print(tree.repoTree)
    print(tree.content)


    
    

        
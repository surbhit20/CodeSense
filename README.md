
Navigating large codebases can be overwhelming, whether you're trying to understand a package, debug a product, or onboard to a new project.

> **CodeSense: *Every repo, finally making sense***
>
> **CodeSense** is your intelligent guide for seamless navigation of GitHub repositories. It transforms the way you explore codebases, helping you save time and gain clarity.

## How It Works

1. **Enter a GitHub URL** — or type `sample` to try it on the CodeSense repo itself
2. **Explore the interactive graph** — a live vis.js tree shows every file and directory, pannable and zoomable
3. **Click any file node** — the AI instantly explains what the file does and its role in the codebase
4. **Ask anything** — use the chat to query the LLM about architecture, data flow, or any file in the repo

## Setup

### Prerequisites
- Python 3.10+
- OpenAI API key

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/surbhit20/CodeSense.git
   cd CodeSense
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set your OpenAI API key**

   Create a `.env` file at the project root:
   ```
   OPENAI_API_KEY=your_api_key_here
   ```

4. **Build the C++ scanner (optional — improves performance on large repos)**
   ```bash
   make build
   ```

5. **Run the app**
   ```bash
   chainlit run app.py --watch
   ```

6. **Open** `http://localhost:8000`

## Technical Overview

### Architecture

CodeSense is a Chainlit application with a Python backend and a custom JavaScript graph panel injected via Chainlit's `custom_js` hook.

| Component | Technology |
|---|---|
| Chat interface | [Chainlit](https://chainlit.io) 2.x |
| Graph visualization | [vis.js Network](https://visjs.github.io/vis-network/) (iframe, `public/graph.html`) |
| LLM | OpenAI (GPT, configurable in `src/LLM.py`) |
| Repo cloning | GitPython |
| File scanning | Python BFS + optional C++17 scanner (`src/scanner.cpp`) |

### Key Files

```
app.py               — Chainlit entry point: chat handlers, session management
src/
  LLM.py             — OpenAI client, function-calling loop (retriever tool)
  treeparser.py      — BFS directory parser; builds file tree + content index
  prompt.py          — System and generation prompt templates
  tools.json         — OpenAI function schema for the retriever tool
  utils.py           — clone() helper (GitPython)
  scanner.cpp        — Optional C++17 scanner for faster file enumeration
public/
  graph.html         — Standalone vis.js graph page (loaded in iframe)
  custom.js          — Injected into Chainlit page: creates graph panel, relays node clicks
.chainlit/
  config.toml        — Chainlit configuration (custom_js, UI settings)
```

### How the Graph Communicates with Python

```
Python                  custom.js (Chainlit page)      graph.html (iframe)
  |                             |                              |
  |-- send_window_message ----> |                              |
  |   {type:'initGraph',        |-- postMessage(data) -------> |
  |    nodes, edges}            |                              |-- renders vis.js graph
  |                             |                              |
  |                             |          (node click)        |
  | <-- @on_window_message ---- | <-- window.parent.postMsg -- |
  |   {type:'nodeClick',        |                              |
  |    id: filepath}            |                              |
  |-- triggers file analysis    |                              |
```

### RAG with Function Calling

The LLM receives the full repository tree as context in its system prompt. When a user clicks a file or asks a question, the model invokes a `retriever` tool (defined in `tools.json`) to fetch file contents on-demand. This keeps the context window small while still giving the model access to any file in the repo.

### C++ Scanner

For large repositories, `src/scanner.cpp` provides a faster alternative to Python's `os.listdir` BFS. It's compiled to `src/libscanner.so` via `make build` and loaded at runtime via `ctypes`. If the shared library isn't present, the app falls back to pure Python silently.

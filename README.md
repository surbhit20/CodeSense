

Navigating large codebases can be overwhelming, whether you're trying to understand a package, debug a product, or steal someone else's work off GitHub. 

This challenge often leaves *developers feeling lost*, especially newcomers to a project. 

When I joined my previous company, I faced the same hurdles-deciphering a massive codebase with minimal guidance, all while hesitating to interrupt busy senior colleagues.

> Enter **CodeSense: *Every Every repo, finally making sense***
> 
> **CodeSense** is your intelligent guide for seamless navigation of GitHub repositories. It transforms the way you explore codebases, helping you save time and gain clarity.

## **How CodeSense Changes the Game**

### **Repository Input**

Users simply provide the GitHub repository they want to explore.

### **Interactive Codebase Mapping**

Behind the scenes, **CodeSense** uses a **Retrieval-Augmented Generation (RAG)** system to map the entire codebase into an intuitive, tree-like structure. This structure offers a clearer, more navigable alternative to GitHub's native interface.

The app uses a Retrieval-Augmented Generation (RAG) system to create a tree-like structure of your repository. This map provides an overview of the codebase at a glance, so you can easily locate and access specific files.

### **LLM-Powered Chat**

* **File Insights:** Clicking on any file (a node in the tree) triggers an explanation from the LLM assistant. You'll receive a brief description of the file and its role in the codebase.
* **Chat Interaction:** A separate chat tab enables you to query the LLM directly about the codebase for deeper insights.

## **Why CodeSense?**
* **Ease of Navigation:** Instantly visualize the codebase structure, making exploration intuitive.
* **AI-Powered Guidance:** Understand files and their roles without needing constant help from teammates.
* **Developer-Friendly:** Perfect for onboarding, debugging, or simply learning how complex projects work.

> **CodeSense isn't just a tool.**
> 
> It's a companion for developers navigating the complexities of modern repositories. Whether you're a junior developer getting started or a senior engineer exploring new projects, **CodeSense** helps you move from confusion to clarity with ease.

## **Setup & Installation**

### **Prerequisites**
- Python 3.8 or higher
- OpenAI API key

### **Installation Steps**

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd CodeSense
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure environment variables**
   ```bash
   cp .env.example .env
   ```
   
   Edit `.env` and add your OpenAI API key:
   ```
   OPENAI_API_KEY=your_actual_api_key_here
   ```

4. **Run the application**
   ```bash
   streamlit run app.py
   ```

5. **Access the app**
   
   Open your browser and navigate to `http://localhost:8501`

### **Usage**

1. When the app opens, enter the GitHub repository URL you want to explore
2. Click "Submit" to clone and analyze the repository
3. Use the **Code Map** tab to visualize the repository structure
4. Click on any file node to get AI-powered insights about that file
5. Use the **Chat** tab to ask questions about the codebase

## **About CodeSense: Technical Overview**

CodeSense is an AI-powered codebase exploration tool built entirely in Python that transforms how developers navigate and understand GitHub repositories. At its core, the application implements a Retrieval-Augmented Generation (RAG) architecture combined with interactive graph visualization to solve the common challenge of getting oriented in unfamiliar codebases. When a developer provides a GitHub repository URL, CodeSense clones the repository locally using GitPython, parses its entire directory structure, and creates an intelligent, queryable representation of the codebase that can be explored both visually and conversationally.

The technical workflow begins with repository cloning through GitPython, a Python library that wraps Git functionality to programmatically download remote repositories. Once cloned, a custom tree parser implemented in `treeparser.py` performs a breadth-first traversal of the directory structure using Python's `collections.deque`. This parser builds a comprehensive map of all files and folders while intelligently filtering out hidden files (those starting with a dot). The parser creates two critical data structures: a hierarchical node-edge graph representing the repository structure, and an indexed dictionary containing the actual content of all text-based files. The content retrieval system uses Python's `mimetypes` module to identify file types, reading source code files, JSON configurations, and even Jupyter notebooks while skipping binary and non-text files. All accessible content is stored in memory for rapid retrieval during user interactions.

The visual interface is powered by Streamlit, a Python framework that enables building interactive web applications using pure Python without writing HTML, CSS, or JavaScript. Streamlit handles the entire web server infrastructure, routing, and state management, exposing a declarative API for creating sophisticated UIs. The application uses Streamlit's tab-based layout to separate the code visualization from the chat interface, and leverages session state management to persist the parsed repository tree, conversation history, and AI model instance throughout the user's exploration session. For the interactive graph visualization, the application integrates streamlit-flow-component, a library that wraps React Flow to bring powerful node-edge graph rendering into the Streamlit ecosystem. Each file and directory in the repository is represented as a draggable node, with animated edges depicting parent-child relationships. Users can pan, zoom, and click on nodes to explore the structure intuitively, with the tree layout algorithm positioning nodes hierarchically from left to right.

The intelligence layer is powered by OpenAI's GPT models (defaulting to GPT-5, though configurable) accessed through the official OpenAI Python client library. What makes CodeSense particularly powerful is its implementation of function calling, an OpenAI feature that allows the language model to invoke predefined tools during its reasoning process. The system defines a retriever function through a JSON schema in `tools.json`, which enables the AI to fetch specific file contents on-demand rather than loading the entire codebase into its context window. This architectural decision makes the system scalable for repositories of any size. The LLM receives carefully engineered system prompts defined in `prompt.py` that instruct it to act as an intelligent code exploration assistant. These prompts provide the model with the complete repository tree structure as context and explain how to use the retriever tool effectively. When a user clicks on a file node in the visual interface, the application automatically sends a generation prompt to the AI, which invokes the retriever function to fetch the file content and generates a concise explanation of the file's purpose, key components, and role within the larger codebase. For open-ended questions in the chat interface, the LLM autonomously decides which files to retrieve based on the query, using both the repository structure and its programming knowledge to provide comprehensive, contextual answers.

The codebase follows a modular architecture with clear separation of concerns across six main Python files. The `app.py` file serves as the entry point, orchestrating the Streamlit interface, handling user interactions, and managing the flow between code visualization and chat modes. The `LLM.py` module encapsulates all AI model communication, implementing a message history manager, handling function calls, and providing a clean API for querying the model. The `treeparser.py` module contains the repository parsing logic and content indexing system, exposing methods to build the tree structure and retrieve file contents. The `prompt.py` file stores template strings for system prompts and generation instructions, keeping prompt engineering separate from application logic. The `utils.py` module provides utility functions like the repository cloning operation, which uses `shutil` to clean up any existing directory before cloning. Finally, `tools.json` defines the OpenAI function calling schema in a declarative format that specifies the retriever tool's parameters and purpose.

Environment configuration is managed through python-dotenv, which loads sensitive information like OpenAI API keys from `.env` files, following security best practices by keeping credentials separate from source code. The application also leverages several Python standard library modules: `pathlib` for modern, object-oriented file path handling; `os` for file system operations; `json` for parsing structured data files and function call arguments; and `mimetypes` for intelligent file type detection. This combination of external dependencies and standard library functionality creates a robust, maintainable system without excessive complexity.

From a user experience perspective, CodeSense offers two complementary modes of exploration. The Code Map tab presents the repository as an interactive, zoomable tree where developers can click any file to instantly receive an AI-generated explanation of its purpose and contents. The Chat tab enables freeform conversation about the codebase, where users can ask architectural questions, trace data flows between files, or understand design patterns. The session state management ensures that the AI maintains context across multiple queries, building upon previous explanations and referencing earlier parts of the conversation. This creates a seamless, intelligent exploration experience that feels like pair programming with an expert who has perfect knowledge of the entire repository. The entire system is designed to minimize cognitive load for developers, transforming the often overwhelming task of understanding new codebases into an intuitive, guided exploration where both visual and conversational interfaces work together to build comprehensive understanding quickly and effectively.

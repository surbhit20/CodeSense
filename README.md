

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

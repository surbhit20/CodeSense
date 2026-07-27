import os
import json
import asyncio
from dotenv import load_dotenv
load_dotenv()

import chainlit as cl
from src.treeparser import Tree
from src.LLM import LLM
from src.utils import clone

SAMPLE_REPO_URL = "https://github.com/surbhit20/CodeSense.git"
CLONE_DIR = "/tmp/codesense-repo"


async def render_tree(code_tree: Tree):
    graph_data = code_tree.get_graph_data()
    await cl.send_window_message({"type": "initGraph", **graph_data})
    files = list(code_tree.content.keys())
    actions = [
        cl.Action(name="analyze_file", payload={"filepath": f}, label=f.replace(CLONE_DIR + "/", ""))
        for f in files[:25]
    ]
    if actions:
        await cl.Message(
            content="Graph loaded. Click a node in the panel, or use the buttons below:",
            actions=actions,
        ).send()


@cl.on_chat_start
async def on_chat_start():
    try:
        await _on_chat_start()
    except Exception as e:
        import traceback
        await cl.Message(content=f"Startup error: {e}\n```\n{traceback.format_exc()}\n```").send()

async def _on_chat_start():
    res = await cl.AskUserMessage(
        content=(
            "**Welcome to CodeSense!** Navigate any GitHub repository with AI.\n\n"
            "Enter a GitHub URL — or type **`sample`** to try it on CodeSense itself:"
        ),
        timeout=300,
    ).send()

    if not res:
        await cl.Message(content="Timed out. Refresh to restart.").send()
        return

    url = res["output"].strip()
    repo_url = SAMPLE_REPO_URL if url.lower() == "sample" else url

    status_msg = await cl.Message(content=f"Cloning `{repo_url}`...").send()
    success = await asyncio.to_thread(clone, repo_url, CLONE_DIR)
    if not success:
        await cl.Message(content="Failed to clone. Check the URL and try again.").send()
        return

    status_msg.content = f"Successfully cloned `{repo_url}`."
    await status_msg.update()

    code_tree = Tree(CLONE_DIR)
    model = LLM(codeTree=code_tree)
    cl.user_session.set("codeTree", code_tree)
    cl.user_session.set("model", model)
    cl.user_session.set("node", None)

    await render_tree(code_tree)
    await cl.Message(
        content="Click a file above to analyze it, or ask me anything about the codebase."
    ).send()


@cl.action_callback("analyze_file")
async def on_file_analyze(action: cl.Action):
    filepath = action.payload["filepath"]
    code_tree = cl.user_session.get("codeTree")
    if not os.path.isfile(filepath):
        await cl.Message(content=f"Could not find `{filepath}` on disk.").send()
        return

    model = LLM(codeTree=code_tree)
    cl.user_session.set("model", model)
    cl.user_session.set("node", filepath)

    async with cl.Step(name=f"Analyzing {filepath.replace(CLONE_DIR + "/", "")}", type="tool") as step:
        step.input = filepath
        response = await asyncio.to_thread(model.call, filepath=filepath)
        step.output = response

    await cl.Message(content=response).send()


@cl.on_window_message
async def on_window_message(message: str):
    try:
        data = json.loads(message) if isinstance(message, str) else message
    except (json.JSONDecodeError, TypeError):
        return
    if data.get("type") != "nodeClick":
        return
    filepath = data.get("id", "")
    code_tree = cl.user_session.get("codeTree")
    if not code_tree or not os.path.isfile(filepath):
        return
    model = LLM(codeTree=code_tree)
    cl.user_session.set("model", model)
    cl.user_session.set("node", filepath)
    async with cl.Step(name=f"Analyzing {filepath.replace(CLONE_DIR + "/", "")}", type="tool") as step:
        step.input = filepath
        response = await asyncio.to_thread(model.call, filepath=filepath)
        step.output = response
    await cl.Message(content=response).send()


@cl.on_message
async def on_message(message: cl.Message):
    model = cl.user_session.get("model")
    if model is None:
        await cl.Message(content="No repository loaded. Please restart the chat.").send()
        return

    async with cl.Step(name="CodeSense", type="llm") as step:
        step.input = message.content
        response = await asyncio.to_thread(model.call, prompt=message.content)
        step.output = response

    await cl.Message(content=response).send()

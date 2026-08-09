import os
import json
import asyncio
from dotenv import load_dotenv
load_dotenv()

import chainlit as cl
from chainlit.server import app as chainlit_app
from src.treeparser import Tree
from src.LLM import LLM
from src.utils import clone

# Chainlit serves custom_js/custom_css from /public via a plain FileResponse
# with no Cache-Control header, so browsers fall back to heuristic caching
# and can keep serving a stale copy indefinitely after a deploy. Force
# revalidation instead — FileResponse already sets ETag/Last-Modified, so a
# deploy still only costs a cheap conditional-GET, not a full refetch.
#
# Guarded because `chainlit run --watch` re-executes this whole module on
# *any* file change (not just app.py) once the server has already started
# — Starlette refuses to add middleware after that point and raises
# RuntimeError. Harmless to skip on reload since the first registration is
# already live; a real deploy only ever runs this once anyway.
try:
    @chainlit_app.middleware("http")
    async def no_cache_public_assets(request, call_next):
        response = await call_next(request)
        if request.url.path.startswith("/public/"):
            response.headers["Cache-Control"] = "no-cache"
        return response
except RuntimeError:
    pass

SAMPLE_REPO_URL = "https://github.com/surbhit20/CodeSense.git"
CLONE_DIR = "/tmp/codesense-repo"

FAQ_QUESTIONS = [
    "What is this repo about?",
    "What's the overall architecture?",
    "How do I run this project?",
    "What are the main dependencies?",
]


def repo_display_name(repo_url: str) -> str:
    """The graph's root node needs the actual repo's name — CLONE_DIR is a
    fixed local path every repo gets cloned into, so Tree's own root.name
    is always "codesense-repo" regardless of what was actually cloned."""
    name = repo_url.rstrip("/").rsplit("/", 1)[-1]
    if name.endswith(".git"):
        name = name[:-4]
    return name or repo_url


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
    cl.user_session.set("awaiting_repo", True)
    welcome_msg = cl.Message(
        content="**Welcome to CodeSense!**",
        actions=[cl.Action(name="sample_repo", payload={}, label="Sample this repo!")],
    )
    await welcome_msg.send()
    cl.user_session.set("welcome_msg", welcome_msg)


async def load_repo(repo_url: str, user_echo: str | None = None):
    """Clones repo_url and wires up the session — shared by the sample-repo
    button and by typing a URL directly. Guarded by the same busy flag as
    stream_reply so a second clone can't race an in-flight one.

    user_echo: a button click has no chat bubble of its own the way typing
    does, so pass the text to show as if the user had typed it themselves.
    Leave unset when the user actually did type (on_message) — there's
    already a real bubble for that."""
    if cl.user_session.get("busy"):
        return

    cl.user_session.set("busy", True)
    try:
        cl.user_session.set("awaiting_repo", False)

        # Matches ChatGPT's own landing state: the big centered greeting is
        # only there until the very first message, then it's gone for good
        # — not left behind as a shrunk chat bubble.
        welcome_msg = cl.user_session.get("welcome_msg")
        if welcome_msg:
            await welcome_msg.remove()
            cl.user_session.set("welcome_msg", None)

        if user_echo:
            await cl.Message(content=user_echo, type="user_message").send()

        status_msg = await cl.Message(content=f"Cloning `{repo_url}`...").send()
        success = await asyncio.to_thread(clone, repo_url, CLONE_DIR)
        if not success:
            await cl.Message(content="Failed to clone. Check the URL and try again.").send()
            cl.user_session.set("awaiting_repo", True)
            return

        status_msg.content = f"Successfully cloned `{repo_url}`."
        await status_msg.update()

        code_tree = Tree(CLONE_DIR, display_name=repo_display_name(repo_url))
        model = LLM(codeTree=code_tree)
        cl.user_session.set("codeTree", code_tree)
        cl.user_session.set("model", model)
        cl.user_session.set("node", None)

        await render_tree(code_tree)
        faq_actions = [
            cl.Action(name="ask_question", payload={"question": q}, label=q)
            for q in FAQ_QUESTIONS
        ]
        await cl.Message(
            content="Click a file above to analyze it, ask me anything, or try one of these:",
            actions=faq_actions,
        ).send()
    finally:
        cl.user_session.set("busy", False)


@cl.action_callback("sample_repo")
async def on_sample_repo(action: cl.Action):
    await load_repo(SAMPLE_REPO_URL, user_echo="Sample this repo!")


# Real token-generation speed varies (fast models, network bursts) and can
# render as an instant wall of text rather than something being "written".
# A small fixed delay per chunk paces it to a natural reading/typing speed
# regardless of how fast the tokens actually arrived.
STREAM_PACE_SECONDS = 0.02


async def stream_reply(model: LLM, step_name: str, step_type: str, *, filepath=None, prompt=None, user_echo=None):
    """Streams the LLM's response into a live message, wrapped in a Step
    for the tool-call trace. Guarded by a per-session busy flag so a second
    request can't run concurrently against the same model/message history.

    user_echo: text to show as if the user had typed it — a button click
    (analyze a file, ask a suggested question) has no chat bubble of its
    own otherwise, which reads as the assistant replying to nothing."""
    if cl.user_session.get("busy"):
        return

    cl.user_session.set("busy", True)
    await cl.send_window_message({"type": "setBusy", "busy": True})
    try:
        if user_echo:
            await cl.Message(content=user_echo, type="user_message").send()

        async with cl.Step(name=step_name, type=step_type) as step:
            step.input = filepath or prompt
            await step.update()

            # The first completion call often just decides to call the
            # retriever tool and streams no visible content — without this,
            # the message sits blank for that whole round trip. Its text
            # doubles as a live "what is it doing right now" indicator,
            # updated as each file is fetched.
            thinking = cl.Message(content="Thinking…")
            await thinking.send()

            msg = cl.Message(content="")
            first_token = True
            async for kind, payload in model.call_stream(filepath=filepath, prompt=prompt):
                if kind == 'tool_call':
                    short_name = payload.replace(CLONE_DIR + '/', '')
                    if first_token:
                        thinking.content = f"Reading `{short_name}`…"
                        await thinking.update()
                    # A nested step under the parent — this is what makes the
                    # chain of thought visible: expanding the parent later
                    # shows the sequence of files it read, not just the
                    # final input/output. Named after the file alone, not
                    # "Reading X" — Chainlit's collapsed label is always
                    # "Used {name}", so a verb in the name doubles up.
                    async with cl.Step(name=short_name, type="tool") as tool_step:
                        tool_step.output = "Fetched"
                    continue

                if first_token:
                    await thinking.remove()
                    await msg.send()
                    first_token = False
                await msg.stream_token(payload)
                await asyncio.sleep(STREAM_PACE_SECONDS)

            if first_token:
                await thinking.remove()
                await msg.send()

            await msg.update()
            step.output = msg.content
    finally:
        cl.user_session.set("busy", False)
        await cl.send_window_message({"type": "setBusy", "busy": False})


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

    name = filepath.replace(CLONE_DIR + "/", "")
    await stream_reply(
        model, name, "tool", filepath=filepath, user_echo=f"What is inside `{name}`?"
    )


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

    name = filepath.replace(CLONE_DIR + "/", "")
    await stream_reply(
        model, name, "tool", filepath=filepath, user_echo=f"What is inside `{name}`?"
    )


@cl.action_callback("ask_question")
async def on_ask_question(action: cl.Action):
    question = action.payload["question"]
    model = cl.user_session.get("model")
    if model is None:
        await cl.Message(content="No repository loaded. Please restart the chat.").send()
        return

    await stream_reply(model, question, "llm", prompt=question, user_echo=question)


@cl.on_message
async def on_message(message: cl.Message):
    if cl.user_session.get("awaiting_repo"):
        url = message.content.strip()
        repo_url = SAMPLE_REPO_URL if url.lower() == "sample" else url
        await load_repo(repo_url)
        return

    model = cl.user_session.get("model")
    if model is None:
        await cl.Message(content="No repository loaded. Please restart the chat.").send()
        return

    await stream_reply(model, "CodeSense", "llm", prompt=message.content)

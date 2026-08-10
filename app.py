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

# Chainlit serves /public, /logo, /favicon, and /avatars/* via a plain
# FileResponse with no Cache-Control header, so browsers fall back to
# heuristic caching and can keep serving a stale copy indefinitely after
# a deploy — the logo/favicon swap was invisible in an already-open
# browser for exactly this reason. Force revalidation instead —
# FileResponse already sets ETag/Last-Modified, so a deploy still only
# costs a cheap conditional-GET, not a full refetch.
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
        path = request.url.path
        if path.startswith("/public/") or path in ("/logo", "/favicon") or path.startswith("/avatars/"):
            response.headers["Cache-Control"] = "no-cache"
        return response
except RuntimeError:
    pass

CLONE_DIR = "/tmp/codesense-repo"

FAQ_QUESTIONS = [
    "What is this repo about?",
    "What's the overall architecture?",
    "How do I run this project?",
    "What are the main dependencies?",
]

# Cosmetic only — two recognizable flagship/mini models per major provider,
# so the picker doesn't read as an Anthropic-only afterthought. Whichever
# one gets picked, every request still goes to the one model LLM.py is
# actually wired up to (see on_message); there's no per-provider API
# integration behind this.
MODEL_OPTIONS = [
    ("claude-opus-5", "Claude Opus 5", "/public/model-icons/anthropic.svg"),
    ("claude-sonnet-5", "Claude Sonnet 5", "/public/model-icons/anthropic.svg"),
    ("gpt-5.1", "GPT-5.1", "/public/model-icons/openai.svg"),
    ("gpt-5.1-mini", "GPT-5.1 mini", "/public/model-icons/openai.svg"),
    ("grok-4", "Grok 4", "/public/model-icons/xai.svg"),
    ("grok-4-mini", "Grok 4 mini", "/public/model-icons/xai.svg"),
    ("gemini-3-pro", "Gemini 3 Pro", "/public/model-icons/gemini.svg"),
    ("gemini-3-flash", "Gemini 3 Flash", "/public/model-icons/gemini.svg"),
]

# A handful of well-known repos, picked for being small/clean enough to
# render as a readable graph rather than the unusable "smear" a huge
# monorepo produces (see the buck2 graph-scalability fix) — not a
# ranking, just repos most people will recognize by name.
STARTER_REPOS = [
    "https://github.com/pallets/flask",
    "https://github.com/psf/requests",
    "https://github.com/karpathy/nanoGPT",
    "https://github.com/expressjs/express",
]


def _owner_repo(repo_url: str) -> str:
    """"owner/repo" slug from a GitHub URL — recognizable at a glance,
    unlike a project's marketing name (not everyone knows "nanoGPT" is
    karpathy's), and it doubles as a preview of what you're about to type."""
    owner, repo = repo_url.rstrip("/").split("/")[-2:]
    return f"{owner}/{repo}"


@cl.set_starters
async def set_starters():
    return [
        cl.Starter(label=f"Explore {_owner_repo(url)}", message=url, icon="/public/github.svg")
        for url in STARTER_REPOS
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

    # A collapsed-by-default step rather than one button per file — a flat
    # wall of ~25 buttons doesn't scale and duplicates what the graph panel
    # already does (click a node to analyze that file). This is just a
    # lightweight "here's what's in scope" receipt, expandable for anyone
    # who wants the exact file list without opening the graph.
    files = sorted(code_tree.to_display_path(f) for f in code_tree.content.keys())
    if not files:
        return
    step = cl.Step(name=f"{len(files)} files", type="run")
    step.output = "```\n" + "\n".join(files) + "\n```"
    await step.send()


@cl.on_chat_start
async def on_chat_start():
    try:
        await _on_chat_start()
    except Exception as e:
        import traceback
        await cl.Message(content=f"Startup error: {e}\n```\n{traceback.format_exc()}\n```").send()

async def _on_chat_start():
    # No welcome message here on purpose: Chainlit only renders its
    # starters UI (and the landing-state logo) while the thread has zero
    # messages — sending so much as a single cl.Message flips it into a
    # regular chat view and the starters never show up. The "explore a
    # codebase" prompt lives in the composer placeholder instead (see
    # custom.js), so the landing state stays message-free.
    cl.user_session.set("awaiting_repo", True)

    # Modes render as a picker directly in the composer (unlike
    # ChatSettings, which is tucked behind a separate gear-icon dialog) —
    # a better fit for something meant to be seen and switched often.
    # There's no on-change hook for modes; the current pick only arrives
    # attached to the next cl.Message the user actually sends (see
    # on_message), so nothing needs wiring up here beyond registering
    # the options.
    await cl.context.emitter.set_modes([
        cl.Mode(
            id="model",
            name="Model",
            options=[
                cl.ModeOption(id=option_id, name=name, icon=icon, default=(i == 0))
                for i, (option_id, name, icon) in enumerate(MODEL_OPTIONS)
            ],
        )
    ])


async def load_repo(repo_url: str):
    """Clones repo_url and wires up the session — shared by starter clicks
    and by typing a URL directly (both arrive here via on_message, so
    there's already a real chat bubble for the input either way). Guarded
    by the same busy flag as stream_reply so a second clone can't race an
    in-flight one."""
    if cl.user_session.get("busy"):
        return

    cl.user_session.set("busy", True)
    try:
        cl.user_session.set("awaiting_repo", False)

        success = await asyncio.to_thread(clone, repo_url, CLONE_DIR)
        if not success:
            await cl.Message(content="Failed to clone. Check the URL and try again.").send()
            cl.user_session.set("awaiting_repo", True)
            return

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
            content="Click a node in the graph to analyze a file, ask me anything, or try one of these:",
            actions=faq_actions,
        ).send()
    finally:
        cl.user_session.set("busy", False)


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

        # Managed manually (no `async with`) so this step never becomes the
        # "ambient" step — entering it via `async with` registers it in
        # Chainlit's context var, which then force-parents *any* cl.Message
        # or cl.Step created inside the block, including the final answer.
        # That nested the visible answer text inside this step's collapsible
        # dropdown. Explicit parent_id on the tool sub-steps below still
        # nests those on purpose, for the chain-of-thought trace.
        #
        # Sending is deferred until the first content token (rather than
        # done here) — sending it now would show a completed-looking
        # "Used {name}" row alongside the still-live "Reading {file}…"
        # line below it, which reads as two rows for one in-progress
        # action. Step.id is assigned at construction (a local uuid4),
        # so nested tool sub-steps can already reference it as their
        # parent_id before it's sent.
        #
        # It's flushed right before the answer message's first send()
        # rather than at the very end — Chainlit orders elements by
        # arrival, not by when the Python object was constructed, so
        # sending it after the (already-sent) message would make the
        # step show up below the answer instead of above it.
        step = cl.Step(name=step_name, type=step_type)
        step.input = filepath or prompt
        pending_tool_steps = []
        step_sent = False

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
                # Queued (or, once the parent's already been sent, sent
                # right away) rather than always sent immediately — see
                # note above.
                tool_step = cl.Step(name=short_name, type="tool", parent_id=step.id)
                tool_step.output = "Fetched"
                if step_sent:
                    await tool_step.send()
                else:
                    pending_tool_steps.append(tool_step)
                continue

            if first_token:
                await thinking.remove()
                # Parent before children before the answer, so arrival
                # order in the transcript is: step, its nested trace,
                # then the answer.
                await step.send()
                for tool_step in pending_tool_steps:
                    await tool_step.send()
                step_sent = True
                await msg.send()
                first_token = False
            await msg.stream_token(payload)
            await asyncio.sleep(STREAM_PACE_SECONDS)

        if first_token:
            await thinking.remove()
            await step.send()
            for tool_step in pending_tool_steps:
                await tool_step.send()
            step_sent = True
            await msg.send()

        await msg.update()
        step.output = msg.content
        await step.update()
    finally:
        cl.user_session.set("busy", False)
        await cl.send_window_message({"type": "setBusy", "busy": False})


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
    # The current mode selection only ever arrives attached to a message
    # like this one — there's no separate on-change event for modes.
    # Cosmetic only (see MODEL_OPTIONS): stored for potential future
    # display, never changes which model actually answers.
    if message.modes:
        cl.user_session.set("selected_model_id", message.modes.get("model"))

    if cl.user_session.get("awaiting_repo"):
        await load_repo(message.content.strip())
        return

    model = cl.user_session.get("model")
    if model is None:
        await cl.Message(content="No repository loaded. Please restart the chat.").send()
        return

    await stream_reply(model, "CodeSense", "llm", prompt=message.content)

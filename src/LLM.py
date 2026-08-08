from openai import AsyncOpenAI
import os
import src.prompt as prompts
import json
from pathlib import Path


class LLM():
    def __init__(self, codeTree, model_name='gpt-5'):
        self.model = AsyncOpenAI(api_key=os.environ["OPENAI_API_KEY"])
        self.model_name = model_name

        self.messages = []
        self.codeTree = codeTree

        self._append('system',
                     prompts.SYSTEM_PROMPT.format(REPO_TREE=self.codeTree.repoTree))

        tools_path = Path(__file__).parent / 'tools.json'
        with open(tools_path, 'r') as f:
            self.tools = json.load(f)

    async def call_stream(self, prompt=None, filepath=None, tool_choice='auto'):
        """Yields ('content', text) chunks as they arrive, and ('tool_call',
        filepath) markers whenever a retriever call is about to run — so a
        caller can surface a live chain-of-thought trace, not just the final
        text. Tool calls are resolved transparently in between (the follow-up
        completion is re-streamed automatically)."""

        if filepath:
            self._append('user', prompts.GENERATION_PROMPT.format(filepath=filepath))

        if prompt:
            self._append('user', prompt)

        while True:
            stream = await self.model.chat.completions.create(
                            model=self.model_name,
                            messages=self.messages,
                            tools=self.tools,
                            tool_choice=tool_choice,
                            stream=True,
                        )

            content_parts = []
            tool_calls_acc = {}

            async for chunk in stream:
                delta = chunk.choices[0].delta

                if delta.content:
                    content_parts.append(delta.content)
                    yield ('content', delta.content)

                if delta.tool_calls:
                    for tc in delta.tool_calls:
                        acc = tool_calls_acc.setdefault(
                            tc.index, {'id': None, 'name': None, 'arguments': ''})
                        if tc.id:
                            acc['id'] = tc.id
                        if tc.function and tc.function.name:
                            acc['name'] = tc.function.name
                        if tc.function and tc.function.arguments:
                            acc['arguments'] += tc.function.arguments

            full_content = ''.join(content_parts) or None

            if not tool_calls_acc:
                self._append('assistant', str(full_content))
                return

            tool_calls = [
                {'id': v['id'], 'type': 'function',
                 'function': {'name': v['name'], 'arguments': v['arguments']}}
                for v in tool_calls_acc.values()
            ]
            self.messages.append(
                {'role': 'assistant', 'content': full_content, 'tool_calls': tool_calls})

            for tool_call in tool_calls:
                if tool_call['function']['name'] == 'retriever':
                    function_args = json.loads(tool_call['function']['arguments'])
                    target_filepath = function_args.get('filepath')
                    yield ('tool_call', target_filepath)
                    function_response = self.codeTree.get(target_filepath)
                    self.messages.append({
                        'tool_call_id': tool_call['id'],
                        'role': 'tool',
                        'name': tool_call['function']['name'],
                        'content': function_response,
                    })

            tool_choice = 'auto'

    def _append(self, role: str, content: str):
        self.messages.append({'role': role,
                              'content': str(content)})
    

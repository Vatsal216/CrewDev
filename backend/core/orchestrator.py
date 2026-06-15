import uuid
import json
import asyncio
from typing import Callable, Awaitable, Optional

from crewai import Task, Crew, Process
from config import settings
from .agent_factory import AgentFactory
from .validator import OutputValidator
from .harness import ProjectHarness
from .token_tracker import TokenTracker
from core.llm.router import LLMRouter
from core.llm.types import ResolvedCall
from memory.short_term import ShortTermMemory
from memory.long_term import LongTermMemory

StreamCallback = Callable[[dict], Awaitable[None]]

MAX_REQUEST_TOKENS = getattr(settings, "max_request_tokens", 200_000)
PASS_THRESHOLD = 0.7


class SubTask:
    def __init__(self, id: str, description: str, agent_type: str,
                 expected_output: str, success_criteria: str,
                 depends_on: Optional[list[str]] = None):
        self.id = id
        self.description = description
        self.agent_type = agent_type
        self.expected_output = expected_output
        self.success_criteria = success_criteria
        self.depends_on = depends_on or []


class Plan:
    def __init__(self, subtasks: list[SubTask], reasoning: str):
        self.subtasks = subtasks
        self.reasoning = reasoning


class MainOrchestrator:
    def __init__(self, project_id: str, session_id: str, resolved: ResolvedCall):
        self.project_id = project_id
        self.session_id = session_id
        self.resolved = resolved
        self.router = LLMRouter()
        self.harness = ProjectHarness(project_id)
        self.factory = AgentFactory(project_id, self.harness)
        self.validator = OutputValidator()
        self._short_mem = None
        self._long_mem = None

    @property
    def short_mem(self) -> ShortTermMemory:
        if self._short_mem is None:
            self._short_mem = ShortTermMemory(self.session_id)
        return self._short_mem

    @property
    def long_mem(self) -> LongTermMemory:
        if self._long_mem is None:
            self._long_mem = LongTermMemory(self.project_id)
        return self._long_mem

    async def process(self, user_message: str, stream_cb: Optional[StreamCallback] = None, skills_block: str = "", attachments_text: str = "", attachment_images=None) -> str:
        tracker = TokenTracker()

        if attachment_images:
            attachments_text = (attachments_text + f"\n[images attached: {len(attachment_images)}]").strip()
        if attachments_text:
            user_message = f"{attachments_text}\n\n{user_message}"

        async def emit(event: dict):
            if stream_cb:
                await stream_cb(event)

        await emit({"type": "status", "message": "Loading project context…"})

        context = await self.harness.get_context()
        history = await self.short_mem.get_context_string(k=settings.short_term_history_k)
        memory_snippets = await self.long_mem.search(user_message, k=3)
        memory_str = "\n".join(memory_snippets) if memory_snippets else ""

        await emit({"type": "status", "message": "Planning task decomposition…"})

        plan = await self._plan(user_message, context, history, memory_str, tracker, skills_block)
        await emit({"type": "plan", "subtasks": [
            {"id": t.id, "agent_type": t.agent_type,
             "description": t.description[:100], "depends_on": t.depends_on}
            for t in plan.subtasks
        ]})

        results: dict[str, str] = {}

        for idx, subtask in enumerate(plan.subtasks):
            if tracker.over_budget(MAX_REQUEST_TOKENS):
                await emit({"type": "budget_stop",
                            "message": f"Token budget hit ({tracker.input_tokens + tracker.output_tokens}). Stopping."})
                break

            upstream = self._gather_upstream(subtask, results)

            await emit({
                "type": "agent_start",
                "task_id": subtask.id,
                "agent_type": subtask.agent_type,
                "description": subtask.description[:150]
            })

            result = await self._execute_with_validation(
                subtask, context, user_message, upstream, emit, tracker
            )
            results[subtask.id] = result

            await emit({
                "type": "agent_done",
                "task_id": subtask.id,
                "agent_type": subtask.agent_type,
                "result_preview": str(result)[:200]
            })

        await emit({"type": "status", "message": "Synthesizing final response…"})

        final = await self._synthesize_streaming(
            user_message, results, context, history, emit, tracker
        )

        await self.short_mem.add("user", user_message)
        await self.short_mem.add("assistant", final)
        await self.long_mem.store(user_message, final, context)
        await self.harness.update(final, self.resolved)

        await emit({"type": "usage", **tracker.summary()})

        return final

    def _gather_upstream(self, subtask: SubTask, results: dict[str, str]) -> str:
        if subtask.depends_on:
            picked = {tid: results[tid] for tid in subtask.depends_on if tid in results}
        else:
            picked = dict(results)
        if not picked:
            return ""
        parts = [f"OUTPUT FROM {tid}:\n{res[:2500]}" for tid, res in picked.items()]
        return "RESULTS FROM PREVIOUS AGENTS (use these):\n\n" + "\n\n".join(parts)

    async def _plan(
        self, user_message: str, context: str, history: str,
        memory: str, tracker: TokenTracker, skills_block: str = ""
    ) -> Plan:
        prompt = f"""You are an AI orchestrator. Decompose the user's request into subtasks for specialized agents.

PROJECT CONTEXT:
{context}

CONVERSATION HISTORY:
{history[-2000:] if history else 'No history'}

RELEVANT MEMORIES:
{memory[:1000] if memory else 'None'}

USER REQUEST:
{user_message}

Available agent types: coder, researcher, web_surfer, file_manager, analyst, tester, devops

Return JSON only:
{{
  "reasoning": "Why you chose these subtasks",
  "subtasks": [
    {{
      "id": "t1",
      "description": "Detailed task description with all context needed",
      "agent_type": "coder",
      "expected_output": "What the agent should produce",
      "success_criteria": "How to judge if the output is good",
      "depends_on": []
    }}
  ]
}}

Guidelines:
- 1-3 subtasks max. Don't over-decompose.
- Use "depends_on" to chain tasks: if t2 needs t1's output, set "depends_on": ["t1"].
- Each subtask self-contained except for declared dependencies.
- Simple questions: 1 subtask, analyst type.
- web_surfer for scraping/browsing specific URLs."""

        if skills_block:
            prompt = f"{skills_block}\n\n{prompt}"

        text, usage = await self.router.acomplete(
            [{"role": "user", "content": prompt}],
            self.resolved,
            max_tokens=1500,
            response_format={"type": "json_object"},
        )
        tracker.add_usage(usage, "planner")
        try:
            data = json.loads(text)
            subtasks = [
                SubTask(
                    id=t.get("id", str(uuid.uuid4())[:8]),
                    description=t["description"],
                    agent_type=t.get("agent_type", "coder"),
                    expected_output=t.get("expected_output", "Complete the task"),
                    success_criteria=t.get("success_criteria", ""),
                    depends_on=t.get("depends_on", []),
                )
                for t in data.get("subtasks", [])
            ]
            return Plan(subtasks=subtasks, reasoning=data.get("reasoning", ""))
        except Exception:
            inferred_type = self.factory.infer_agent_type(user_message)
            return Plan(
                subtasks=[SubTask(
                    id="t1",
                    description=user_message,
                    agent_type=inferred_type,
                    expected_output="Complete the user's request",
                    success_criteria=""
                )],
                reasoning="Fallback single-task plan"
            )

    async def _execute_with_validation(
        self,
        subtask: SubTask,
        context: str,
        user_request: str,
        upstream: str,
        emit: Callable,
        tracker: TokenTracker,
    ) -> str:
        description = subtask.description
        if context:
            description += f"\n\nProject context:\n{context[:2000]}"
        if upstream:
            description += f"\n\n{upstream}"

        output_str = ""
        for attempt in range(settings.max_validation_iter):
            if tracker.over_budget(MAX_REQUEST_TOKENS):
                await emit({"type": "budget_stop", "task_id": subtask.id,
                            "message": "Token budget hit mid-task."})
                break

            if attempt > 0:
                await emit({"type": "retry", "task_id": subtask.id, "attempt": attempt + 1})

            try:
                agent = self.factory.create(subtask.agent_type, self.resolved, extra_context=context)
                crew = Crew(
                    agents=[agent],
                    tasks=[Task(
                        description=description,
                        agent=agent,
                        expected_output=subtask.expected_output,
                    )],
                    process=Process.sequential,
                    verbose=False,
                )
                output = await asyncio.to_thread(crew.kickoff)
                output_str = str(output)

                usage = getattr(output, "token_usage", None)
                if usage:
                    tracker.add(
                        input_tokens=getattr(usage, "prompt_tokens", 0) or 0,
                        output_tokens=getattr(usage, "completion_tokens", 0) or 0,
                        agent=subtask.agent_type,
                        model=self.resolved.model,
                    )
            except Exception as e:
                output_str = f"Agent execution error: {e}"

            verdict = await self.validator.evaluate(
                output_str, subtask.description,
                subtask.success_criteria, user_request,
                resolved=self.resolved,
            )

            await emit({
                "type": "validation",
                "task_id": subtask.id,
                "passed": verdict.passed,
                "score": round(verdict.score, 2),
                "feedback": verdict.feedback,
                "attempt": attempt + 1
            })

            if verdict.passed or verdict.score >= PASS_THRESHOLD:
                return output_str

            description += (f"\n\nPREVIOUS ATTEMPT {attempt+1} FEEDBACK:\n"
                           f"{verdict.feedback}\nFix these issues.")

        return output_str

    async def _synthesize_streaming(
        self, user_message: str, results: dict[str, str],
        context: str, history: str, emit: Callable, tracker: TokenTracker
    ) -> str:
        if len(results) == 1:
            text = list(results.values())[0]
            await self._stream_text(text, emit)
            return text

        results_str = "\n\n".join(
            f"TASK {tid}:\n{res[:2000]}" for tid, res in results.items()
        )
        prompt = f"""Synthesize these agent outputs into a single coherent response.

USER REQUEST:
{user_message}

AGENT RESULTS:
{results_str}

Write a clear, well-formatted response with code blocks where relevant.
Be concise but complete. Don't repeat information."""

        full_text, usage = await self.router.astream(
            [{"role": "user", "content": prompt}],
            self.resolved,
            max_tokens=4000,
            emit=emit,
        )
        tracker.add_usage(usage, "synthesizer")
        return full_text

    async def _stream_text(self, text: str, emit: Callable, chunk: int = 24):
        for i in range(0, len(text), chunk):
            await emit({"type": "token", "text": text[i:i + chunk]})
            await asyncio.sleep(0.01)
